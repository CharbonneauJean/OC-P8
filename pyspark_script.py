#!/usr/bin/env python3
"""
EMR Optimized Fruit Classification Script using Transfer Learning
This script is designed to run on AWS EMR clusters with PySpark
"""

import os
import sys
import time
from datetime import datetime
import platform
import warnings
import json
import pickle
import numpy as np
from PIL import Image
import io
from typing import List, Tuple, Dict
import boto3
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for EMR
import matplotlib.pyplot as plt
import seaborn as sns

# PySpark imports
from pyspark.sql import SparkSession, Row
from pyspark.sql.functions import col, udf, element_at, split, count, when, lit, sqrt, pow as spark_pow
from pyspark.sql.types import ArrayType, FloatType, StringType, IntegerType, BooleanType, BinaryType
from pyspark.ml.feature import StandardScaler, VectorAssembler, StringIndexer, PCA
from pyspark.ml.classification import RandomForestClassifier, LogisticRegression, DecisionTreeClassifier
from pyspark.ml.evaluation import MulticlassClassificationEvaluator
from pyspark.ml import Pipeline
from pyspark.ml.linalg import Vectors, VectorUDT
from pyspark import StorageLevel

# TensorFlow imports
import tensorflow as tf
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.preprocessing import image
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input

# Disable warnings
warnings.filterwarnings('ignore')

# Force TensorFlow to use CPU
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
tf.config.set_visible_devices([], 'GPU')

# Configuration parameters
CONFIG = {
    "batch_size": 64,
    "image_size": (224, 224),
    "num_features": 1280,
    "test_split": 0.2,
    "seed": 42,
    "num_trees": 200,
    "max_depth": 20,
    "min_instances_per_node": 1,
    "feature_subset_strategy": "sqrt",
    "pca_components": 100,
    "pca_variance_threshold": 0.99
}

# S3 paths - using s3:// for EMR native support
DATA_PATH = "s3a://oc-p8-charbonneau-fruits-input/Test1"
RESULTS_PATH = "s3a://oc-p8-charbonneau-fruits-output/Results"

# S3 client for saving results
s3_client = boto3.client('s3')
BUCKET_NAME = "oc-p8-charbonneau-fruits-output"
RESULTS_PREFIX = "Results"

def create_spark_session():
    """Create optimized Spark session for EMR"""
    builder = SparkSession.builder \
        .appName("FruitClassification_TransferLearning_EMR")
    
    # Adjusted EMR-specific configuration for smaller instances
    builder = builder \
        .config("spark.executor.memory", "4g") \
        .config("spark.executor.memoryOverhead", "1g") \
        .config("spark.executor.cores", "2") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .config("spark.sql.execution.arrow.pyspark.enabled", "true") \
        .config("spark.sql.execution.arrow.maxRecordsPerBatch", "10000") \
        .config("spark.python.worker.memory", "2g") \
        .config("spark.python.worker.reuse", "true") \
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
        .config("spark.kryoserializer.buffer.max", "512m") \
        .config("spark.sql.shuffle.partitions", "100") \
        .config("spark.default.parallelism", "100") \
        .config("spark.jars.packages", "org.apache.hadoop:hadoop-aws:3.3.1") \
        .config("spark.dynamicAllocation.enabled", "true") \
        .config("spark.dynamicAllocation.minExecutors", "2") \
        .config("spark.dynamicAllocation.maxExecutors", "10")
    
    spark = builder.getOrCreate()
    
    return spark


def save_plot_to_s3(fig, filename):
    """Save matplotlib figure to S3"""
    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
    buffer.seek(0)
    
    key = f"{RESULTS_PREFIX}/{filename}"
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=buffer.getvalue(),
        ContentType='image/png'
    )
    plt.close(fig)
    return f"s3://{BUCKET_NAME}/{key}"

def extract_mobilenet_features_batch(image_bytes_list, model):
    """Extract features for a batch of images using a pre-loaded model."""
    try:
        batch_features = []
        for image_bytes in image_bytes_list:
            try:
                img = Image.open(io.BytesIO(image_bytes))
                img = img.convert('RGB')
                img = img.resize((224, 224))
                
                img_array = image.img_to_array(img)
                img_array = np.expand_dims(img_array, axis=0)
                img_array = preprocess_input(img_array)
                
                features = model.predict(img_array, verbose=0)
                batch_features.append(features[0].tolist())
            except Exception as e:
                # Use the global CONFIG, not a hardcoded value
                batch_features.append([0.0] * CONFIG["num_features"])
        
        return batch_features
    except Exception as e:
        return [[0.0] * CONFIG["num_features"]] * len(image_bytes_list)

def process_partition(iterator):
    """
    Process a partition of images.
    The model is loaded once per partition for efficiency.
    """
    rows = list(iterator)
    if not rows:
        return iter([])

    # 1. Load model ONCE per partition
    with tf.device('/CPU:0'):
        weights = pickle.loads(broadcast_weights.value)
        config = broadcast_config.value
        base_model = tf.keras.Model.from_config(config)
        base_model.set_weights(weights)

    batch_size = 32  # Or use CONFIG["batch_size"]
    result_rows = []
    
    for i in range(0, len(rows), batch_size):
        batch_rows = rows[i:i+batch_size]
        image_bytes_list = [row.content for row in batch_rows]
        
        # 2. Pass the loaded model to the extraction function
        features_list = extract_mobilenet_features_batch(image_bytes_list, base_model)
        
        for j, row in enumerate(batch_rows):
            result_rows.append(Row(
                path=row.path,
                label=row.label,
                features=features_list[j]
            ))
    
    return iter(result_rows)

def main():
    """Main execution function"""
    print("Starting EMR Fruit Classification Pipeline...")
    print(f"Running on EMR cluster")
    start_time = time.time()
    
    # Initialize Spark
    print("\n1. Initializing Spark Session...")
    initialization_start = time.time()
    spark = create_spark_session()
    sc = spark.sparkContext
    
    # Log Spark configuration
    print(f"Spark version: {spark.version}")
    print(f"Number of executors: {sc._jsc.sc().getExecutorMemoryStatus().size()}")
    initialization_time = time.time() - initialization_start
    
    # Load and broadcast model
    print("\n2. Loading and Broadcasting MobileNetV2 Model...")
    broadcast_start = time.time()
    
    base_model = MobileNetV2(
        input_shape=(224, 224, 3),
        include_top=False,
        weights='imagenet',
        pooling='avg'
    )
    base_model.trainable = False
    
    model_weights = base_model.get_weights()
    model_config = base_model.get_config()
    
    serialized_weights = pickle.dumps(model_weights)
    global broadcast_weights, broadcast_config
    broadcast_weights = sc.broadcast(serialized_weights)
    broadcast_config = sc.broadcast(model_config)
    
    model_load_time = time.time() - broadcast_start
    print(f"Model broadcast completed in {model_load_time:.2f} seconds")
    
    # Load images using s3:// protocol which EMR handles natively
    print("\n3. Loading Images from S3...")
    loading_start = time.time()
    
    try:
        # EMR handles s3:// natively without needing S3A configuration
        images_df = spark.read.format("binaryFile") \
            .option("pathGlobFilter", "*.jpg") \
            .option("recursiveFileLookup", "true") \
            .load(DATA_PATH)
        
        print(f"Successfully loaded images from {DATA_PATH}")
    except Exception as e:
        print(f"Error loading images: {str(e)}")
        print("Attempting alternative approach...")
        
        # Alternative: Use HDFS copy if S3 direct access fails
        # This requires the data to be copied to HDFS first
        hdfs_path = "/tmp/fruit_images"
        print(f"Trying to load from HDFS: {hdfs_path}")
        
        try:
            images_df = spark.read.format("binaryFile") \
                .option("pathGlobFilter", "*.jpg") \
                .option("recursiveFileLookup", "true") \
                .load(hdfs_path)
        except:
            raise Exception("Unable to load images. Please ensure data is accessible.")
    
    images_df = images_df.withColumn('label', element_at(split(col('path'), '/'), -2))
    
    # Validate images
    def validate_image(content):
        try:
            img = Image.open(io.BytesIO(content))
            return img.size[0] > 0 and img.size[1] > 0
        except:
            return False
    
    validate_image_udf = udf(validate_image, BooleanType())
    images_df = images_df.withColumn('is_valid', validate_image_udf(col('content')))
    images_df = images_df.filter(col('is_valid') == True).drop('is_valid')
    images_df.cache()
    
    image_count = images_df.count()
    loading_time = time.time() - loading_start
    print(f"Loaded {image_count} valid images in {loading_time:.2f} seconds")
    
    # Extract features
    print("\n4. Extracting Features using Transfer Learning...")
    feature_extraction_start = time.time()
    
    optimal_partitions = min(sc.defaultParallelism, 50)
    images_df_repartitioned = images_df.repartition(optimal_partitions)
    features_rdd = images_df_repartitioned.rdd.mapPartitions(process_partition)
    features_df = spark.createDataFrame(features_rdd)
    
    array_to_vector_udf = udf(
        lambda x: Vectors.dense(x) if x else Vectors.dense([0.0] * CONFIG["num_features"]), 
        VectorUDT()
    )
    features_vector_df = features_df.select(
        col("path"),
        col("label"),
        array_to_vector_udf(col("features")).alias("features_vector")
    )
    features_vector_df.persist(StorageLevel.MEMORY_AND_DISK)
    processed_count = features_vector_df.count()
    
    feature_extraction_time = time.time() - feature_extraction_start
    print(f"Feature extraction completed in {feature_extraction_time:.2f} seconds")
    
    # PCA Analysis
    print("\n5. Performing PCA Analysis...")
    pca_start = time.time()
    
    label_indexer = StringIndexer(inputCol="label", outputCol="label_index")
    label_indexer_model = label_indexer.fit(features_vector_df)
    indexed_df = label_indexer_model.transform(features_vector_df)
    
    scaler = StandardScaler(
        inputCol="features_vector",
        outputCol="scaled_features",
        withStd=True,
        withMean=False
    )
    scaler_model = scaler.fit(indexed_df)
    scaled_df = scaler_model.transform(indexed_df)
    
    pca = PCA(k=CONFIG["pca_components"], inputCol="scaled_features", outputCol="pca_features")
    pca_model = pca.fit(scaled_df)
    pca_df = pca_model.transform(scaled_df)
    
    explained_variance = pca_model.explainedVariance.toArray()
    cumulative_variance = np.cumsum(explained_variance)
    
    pca_time = time.time() - pca_start
    print(f"PCA completed in {pca_time:.2f} seconds")
    print(f"Total variance explained: {cumulative_variance[-1]:.2%}")
    
    # Create PCA visualization
    print("\n6. Creating Visualizations...")
    
    # PCA 2D visualization
    pca_2d = PCA(k=2, inputCol="scaled_features", outputCol="pca_2d")
    pca_2d_model = pca_2d.fit(scaled_df)
    pca_2d_result = pca_2d_model.transform(scaled_df)
    
    # Sample for visualization (to avoid memory issues)
    sample_size = min(1000, processed_count)
    pca_viz_df = pca_2d_result.select("label", "pca_2d").sample(False, sample_size/processed_count, seed=CONFIG["seed"]).toPandas()
    pca_viz_df['pca_1'] = pca_viz_df['pca_2d'].apply(lambda x: float(x[0]))
    pca_viz_df['pca_2'] = pca_viz_df['pca_2d'].apply(lambda x: float(x[1]))
    
    fig, ax = plt.subplots(figsize=(12, 8))
    sns.scatterplot(data=pca_viz_df, x='pca_1', y='pca_2', hue='label', 
                    palette='viridis', alpha=0.6, s=50, ax=ax)
    ax.set_title('PCA Visualization of MobileNetV2 Features', fontsize=16)
    ax.set_xlabel('First Principal Component')
    ax.set_ylabel('Second Principal Component')
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    
    pca_viz_path = save_plot_to_s3(fig, f"pca_visualization_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
    print(f"PCA visualization saved to: {pca_viz_path}")
    
    # Explained variance plot
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    
    ax1.bar(range(1, min(21, len(explained_variance) + 1)), explained_variance[:20])
    ax1.set_xlabel('Principal Component')
    ax1.set_ylabel('Explained Variance Ratio')
    ax1.set_title('Explained Variance by Component (Top 20)')
    
    ax2.plot(range(1, len(cumulative_variance) + 1), cumulative_variance, 'bo-')
    ax2.axhline(y=CONFIG["pca_variance_threshold"], color='r', linestyle='--',
                label=f'{CONFIG["pca_variance_threshold"]:.0%} threshold')
    ax2.set_xlabel('Number of Components')
    ax2.set_ylabel('Cumulative Explained Variance')
    ax2.set_title('Cumulative Explained Variance')
    ax2.legend()
    
    variance_path = save_plot_to_s3(fig, f"explained_variance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
    print(f"Variance plot saved to: {variance_path}")
    
    # Train model
    print("\n7. Training Random Forest Model...")
    training_start = time.time()
    
    train_df, test_df = pca_df.randomSplit([1-CONFIG["test_split"], CONFIG["test_split"]], 
                                           seed=CONFIG["seed"])
    
    train_count = train_df.count()
    test_count = test_df.count()
    print(f"Training samples: {train_count}, Test samples: {test_count}")
    
    rf = RandomForestClassifier(
        featuresCol="pca_features",
        labelCol="label_index",
        numTrees=CONFIG["num_trees"],
        maxDepth=CONFIG["max_depth"],
        minInstancesPerNode=CONFIG["min_instances_per_node"],
        featureSubsetStrategy=CONFIG["feature_subset_strategy"],
        seed=CONFIG["seed"]
    )
    
    rf_model = rf.fit(train_df)
    training_time = time.time() - training_start
    print(f"Model training completed in {training_time:.2f} seconds")
    
    # Evaluate model
    print("\n8. Evaluating Model Performance...")
    evaluation_start = time.time()
    
    predictions = rf_model.transform(test_df)
    
    evaluator_accuracy = MulticlassClassificationEvaluator(
        labelCol="label_index", predictionCol="prediction", metricName="accuracy"
    )
    evaluator_f1 = MulticlassClassificationEvaluator(
        labelCol="label_index", predictionCol="prediction", metricName="f1"
    )
    
    accuracy = evaluator_accuracy.evaluate(predictions)
    f1_score = evaluator_f1.evaluate(predictions)
    
    evaluation_time = time.time() - evaluation_start
    print(f"Evaluation completed in {evaluation_time:.2f} seconds")
    print(f"Accuracy: {accuracy:.4f} ({accuracy*100:.2f}%)")
    print(f"F1 Score: {f1_score:.4f}")
    
    # Feature importance plot
    feature_importances = rf_model.featureImportances.toArray()
    top_features_idx = np.argsort(feature_importances)[-20:][::-1]
    
    fig, ax = plt.subplots(figsize=(10, 8))
    y_pos = np.arange(len(top_features_idx))
    ax.barh(y_pos, feature_importances[top_features_idx])
    ax.set_yticks(y_pos)
    ax.set_yticklabels([f'PCA_{idx}' for idx in top_features_idx])
    ax.set_xlabel('Importance')
    ax.set_title('Top 20 Most Important PCA Components')
    
    importance_path = save_plot_to_s3(fig, f"feature_importance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
    print(f"Feature importance plot saved to: {importance_path}")
    
    # Ensemble approach
    print("\n9. Training Ensemble Models...")
    ensemble_start = time.time()
    
    lr = LogisticRegression(
        featuresCol="pca_features",
        labelCol="label_index",
        maxIter=100,
        regParam=0.01
    )
    
    dt = DecisionTreeClassifier(
        featuresCol="pca_features",
        labelCol="label_index",
        maxDepth=10,
        seed=CONFIG["seed"]
    )
    
    lr_model = lr.fit(train_df)
    dt_model = dt.fit(train_df)
    
    rf_predictions = rf_model.transform(test_df)
    lr_predictions = lr_model.transform(test_df)
    dt_predictions = dt_model.transform(test_df)
    
    ensemble_predictions = rf_predictions.select("path", "label_index", 
                                               col("prediction").alias("rf_pred")) \
        .join(lr_predictions.select("path", col("prediction").alias("lr_pred")), "path") \
        .join(dt_predictions.select("path", col("prediction").alias("dt_pred")), "path")
    
    ensemble_predictions = ensemble_predictions.withColumn(
        "prediction",
        when((col("rf_pred") == col("lr_pred")) | (col("rf_pred") == col("dt_pred")), col("rf_pred"))
        .when(col("lr_pred") == col("dt_pred"), col("lr_pred"))
        .otherwise(col("rf_pred"))
    )
    
    ensemble_accuracy = evaluator_accuracy.evaluate(ensemble_predictions)
    ensemble_time = time.time() - ensemble_start
    print(f"Ensemble training completed in {ensemble_time:.2f} seconds")
    print(f"Ensemble Accuracy: {ensemble_accuracy:.4f} ({ensemble_accuracy*100:.2f}%)")
    
    # Calculate total time
    total_time = time.time() - start_time
    
    # Prepare results
    results = {
        "platform": {
            "system": platform.system(),
            "is_emr": True,
            "spark_version": spark.version,
            "python_version": sys.version.split()[0],
            "executors": sc._jsc.sc().getExecutorMemoryStatus().size(),
            "default_parallelism": sc.defaultParallelism
        },
        "data": {
            "total_images": image_count,
            "processed_images": processed_count,
            "train_samples": train_count,
            "test_samples": test_count,
            "num_classes": len(label_indexer_model.labels),
            "classes": label_indexer_model.labels
        },
        "feature_extraction": {
            "method": "MobileNetV2 Transfer Learning",
            "input_size": list(CONFIG["image_size"]),
            "feature_dimension": CONFIG["num_features"]
        },
        "pca_analysis": {
            "components_used": CONFIG["pca_components"],
            "variance_explained": float(cumulative_variance[-1])
        },
        "model": {
            "type": "RandomForestClassifier",
            "num_trees": CONFIG["num_trees"],
            "max_depth": CONFIG["max_depth"]
        },
        "performance": {
            "accuracy": float(accuracy),
            "f1_score": float(f1_score),
            "ensemble_accuracy": float(ensemble_accuracy)
        },
        "timing": {
            "initialization": initialization_time,
            "model_broadcast": model_load_time,
            "data_loading": loading_time,
            "feature_extraction": feature_extraction_time,
            "pca_analysis": pca_time,
            "model_training": training_time,
            "evaluation": evaluation_time,
            "ensemble": ensemble_time,
            "total_execution_time": total_time
        },
        "visualizations": {
            "pca_plot": pca_viz_path,
            "variance_plot": variance_path,
            "importance_plot": importance_path
        },
        "timestamp": datetime.now().isoformat()
    }
    
    # Save results to S3
    results_key = f"{RESULTS_PREFIX}/results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=results_key,
        Body=json.dumps(results, indent=2),
        ContentType='application/json'
    )
    
    print(f"\n{'='*80}")
    print(f"EXECUTION SUMMARY")
    print(f"{'='*80}")
    print(f"Total execution time: {total_time:.2f} seconds ({total_time/60:.2f} minutes)")
    print(f"Images processed: {processed_count}")
    print(f"Final accuracy: {accuracy:.2%}")
    print(f"Ensemble accuracy: {ensemble_accuracy:.2%}")
    print(f"\nResults saved to: s3://{BUCKET_NAME}/{results_key}")
    print(f"Visualizations saved to S3:")
    print(f"  - PCA: {pca_viz_path}")
    print(f"  - Variance: {variance_path}")
    print(f"  - Feature Importance: {importance_path}")
    print(f"{'='*80}")
    
    # Cleanup
    broadcast_weights.unpersist()
    broadcast_config.unpersist()
    spark.stop()
    
    print("\nPipeline completed successfully!")

if __name__ == "__main__":
    main()
