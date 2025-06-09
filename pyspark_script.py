# pyspark_script.py

# This script will contain the PySpark code for broadcasting TensorFlow model weights and performing PCA.
# Detailed implementation will follow.




## Diffusion des poids du modèle TensorFlow

# Pour diffuser les poids du modèle TensorFlow, nous allons utiliser la fonctionnalité `broadcast` de Spark. Cela permet d'envoyer une copie en lecture seule d'une variable à chaque nœud du cluster, ce qui est efficace pour les objets volumineux comme les modèles de machine learning. Plutôt que de sérialiser et désérialiser le modèle complet, nous allons sérialiser le modèle en bytes et le diffuser. Chaque worker pourra ensuite charger le modèle à partir de ces bytes.


import tensorflow as tf
from pyspark.sql import SparkSession
from pyspark.sql.functions import pandas_udf, PandasUDFType
from pyspark.sql.types import StructType, StructField, StringType, BinaryType, ArrayType, FloatType
import pandas as pd
import io
from PIL import Image
import numpy as np

# Initialisation de SparkSession
spark = SparkSession.builder \
    .appName("FruitsFeatureExtraction") \
    .config("spark.driver.memory", "4g") \
    .getOrCreate()

# Définition du chemin du modèle MobileNetV2
model_path = "/tmp/MobileNetV2_weights.h5" # Chemin temporaire pour sauvegarder le modèle

# Charger le modèle MobileNetV2 pré-entraîné
model = tf.keras.applications.MobileNetV2(weights='imagenet', include_top=False, input_shape=(224, 224, 3))

# Sauvegarder le modèle pour pouvoir le charger en bytes
model.save(model_path)

# Lire le modèle en bytes
with open(model_path, 'rb') as f:
    model_bytes = f.read()

# Diffuser le modèle en bytes aux workers Spark
broadcasted_model_bytes = spark.sparkContext.broadcast(model_bytes)

# Définition de la fonction UDF pour la featurisation
# Cette fonction sera exécutée sur chaque worker
@pandas_udf(ArrayType(FloatType()), PandasUDFType.SCALAR)
def featurize_image(content: pd.Series) -> pd.Series:
    # Charger le modèle à partir des bytes diffusés
    # Le modèle est chargé une seule fois par worker
    global loaded_model
    if 'loaded_model' not in globals():
        with open("model.h5", "wb") as f:
            f.write(broadcasted_model_bytes.value)
        loaded_model = tf.keras.models.load_model("model.h5")

    def preprocess(img_content):
        img = Image.open(io.BytesIO(img_content)).resize((224, 224))
        img_array = np.array(img).astype(np.float32)
        img_array = tf.keras.applications.mobilenet_v2.preprocess_input(img_array)
        return img_array

    processed_images = np.array([preprocess(c) for c in content])
    features = loaded_model.predict(processed_images)
    return pd.Series(features.reshape(-1, 1280).tolist())

# Exemple d'utilisation (à adapter avec vos données réelles)
# Supposons que vous avez un DataFrame Spark avec une colonne 'image_content' contenant les bytes des images
# data = [("image1.jpg", b"...image_bytes..."), ("image2.jpg", b"...image_bytes...")]
# schema = StructType([StructField("image_name", StringType(), True), StructField("image_content", BinaryType(), True)])
# df = spark.createDataFrame(data, schema)

# df_features = df.withColumn("features", featurize_image(df["image_content"]))
# df_features.show()

# spark.stop()


## Réduction de dimension PCA en PySpark

# Pour la réduction de dimension, nous allons utiliser l'implémentation de PCA (Principal Component Analysis) disponible dans la bibliothèque MLlib de PySpark. Cette étape est cruciale pour réduire la complexité des données tout en conservant l'information essentielle, ce qui est particulièrement utile pour les vecteurs de caractéristiques de grande dimension générés par le modèle MobileNetV2.


from pyspark.ml.feature import PCA
from pyspark.ml.linalg import Vectors, VectorUDT

# Supposons que df_features est le DataFrame obtenu après la featurisation,
# et qu'il contient une colonne 'features' de type ArrayType(FloatType())

# Convertir la colonne 'features' en VectorUDT, nécessaire pour PCA
# Si votre colonne 'features' est déjà un VectorUDT, cette étape n'est pas nécessaire.
# Assurez-vous que la colonne 'features' est de type VectorUDT pour PCA.
# Exemple de conversion si 'features' est un ArrayType(FloatType()):
# from pyspark.sql.functions import udf
# list_to_vector_udf = udf(lambda l: Vectors.dense(l), VectorUDT())
# df_features_vector = df_features.withColumn("features_vector", list_to_vector_udf(df_features["features"]))

# Pour cet exemple, nous allons créer un DataFrame de démonstration
# avec une colonne 'features_vector' de type VectorUDT
data_pca = [
    (Vectors.dense([0.1, 0.2, 0.3, 0.4, 0.5]),),
    (Vectors.dense([0.5, 0.4, 0.3, 0.2, 0.1]),),
    (Vectors.dense([0.2, 0.3, 0.4, 0.5, 0.6]),)
]
schema_pca = StructType([StructField("features_vector", VectorUDT(), True)])
df_pca_demo = spark.createDataFrame(data_pca, schema_pca)

# Initialiser PCA
# k est le nombre de composantes principales à conserver
pca = PCA(k=2, inputCol="features_vector", outputCol="pca_features")

# Entraîner le modèle PCA
model_pca = pca.fit(df_pca_demo)

# Appliquer la transformation PCA
df_pca_result = model_pca.transform(df_pca_demo)

df_pca_result.show(truncate=False)

# Vous pouvez maintenant utiliser df_pca_result.pca_features pour la suite de votre analyse.

# spark.stop()



