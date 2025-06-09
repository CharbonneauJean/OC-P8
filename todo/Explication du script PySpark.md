# Explication du script PySpark

Ce document explique le script PySpark fourni, qui intègre deux fonctionnalités clés pour le traitement des données Big Data : la diffusion des poids d'un modèle TensorFlow et la réduction de dimension via l'Analyse en Composantes Principales (PCA).

## 1. Diffusion des poids du modèle TensorFlow

### Contexte et Problématique

Dans un environnement de calcul distribué comme Apache Spark, l'utilisation de modèles de Machine Learning pré-entraînés, tels que ceux de TensorFlow/Keras, pose un défi. Chaque *worker* (nœud de calcul) du cluster a besoin d'accéder au modèle pour effectuer des inférences (par exemple, l'extraction de caractéristiques d'images). Charger le modèle individuellement sur chaque *worker* peut être inefficace en termes de temps et de ressources, surtout si le modèle est volumineux. De plus, la sérialisation et la désérialisation directes d'objets complexes comme les modèles TensorFlow peuvent être problématiques avec les mécanismes de diffusion standard de Spark.

### Solution : Diffusion des Bytes du Modèle

Pour résoudre ce problème, nous utilisons une approche consistant à sérialiser le modèle TensorFlow en un flux de bytes, puis à diffuser ces bytes à travers le cluster Spark. Chaque *worker* reçoit alors une copie des bytes du modèle, qu'il peut ensuite désérialiser localement pour reconstruire le modèle. Cette méthode est plus robuste et efficace que la diffusion directe de l'objet modèle.

### Détails de l'implémentation

Le script utilise la fonction `spark.sparkContext.broadcast()` pour diffuser les bytes du modèle. Le modèle est d'abord sauvegardé localement dans un fichier (par exemple, au format H5), puis lu en tant que bytes. Ces bytes sont ensuite diffusés.

Une *Pandas UDF* (User-Defined Function) est définie pour encapsuler la logique de featurisation. Cette UDF est cruciale car elle permet d'exécuter du code Python optimisé pour Pandas sur les *workers* Spark. À l'intérieur de l'UDF, une vérification est effectuée pour s'assurer que le modèle n'est chargé qu'une seule fois par *worker* (`if 'loaded_model' not in globals():`). Cela évite des rechargements inutiles et coûteux à chaque appel de l'UDF.

Le processus de featurisation inclut le prétraitement des images (redimensionnement, conversion en tableau NumPy, et application de la fonction de prétraitement spécifique à MobileNetV2) avant de passer les images au modèle pour l'extraction des caractéristiques.

```python
import tensorflow as tf
from pyspark.sql import SparkSession
from pyspark.sql.functions import pandas_udf, PandasUDFType
from pyspark.sql.types import ArrayType, FloatType
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
model = tf.keras.applications.MobileNetV2(weights=\'imagenet\', include_top=False, input_shape=(224, 224, 3))

# Sauvegarder le modèle pour pouvoir le charger en bytes
model.save(model_path)

# Lire le modèle en bytes
with open(model_path, \'rb\') as f:
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
    if \'loaded_model\' not in globals():
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

# Exemple d\'utilisation (à adapter avec vos données réelles)
# Supposons que vous avez un DataFrame Spark avec une colonne \'image_content\' contenant les bytes des images
# data = [("image1.jpg", b"...image_bytes..."), ("image2.jpg", b"...image_bytes...")]
# schema = StructType([StructField("image_name", StringType(), True), StructField("image_content", BinaryType(), True)])
# df = spark.createDataFrame(data, schema)

# df_features = df.withColumn("features", featurize_image(df["image_content"]))
# df_features.show()

# spark.stop()
```

## 2. Réduction de dimension PCA en PySpark

### Contexte et Problématique

Les caractéristiques extraites par des modèles de Deep Learning, comme MobileNetV2, sont souvent de haute dimension (ici, 1280 dimensions). Bien que riches en informations, ces vecteurs de haute dimension peuvent entraîner des problèmes de performance et de stockage, et peuvent rendre les analyses ultérieures plus complexes. La réduction de dimension est une technique essentielle pour condenser ces informations en un ensemble plus petit de variables, tout en minimisant la perte d'informations.

### Solution : PCA avec MLlib

L'Analyse en Composantes Principales (PCA) est une méthode statistique couramment utilisée pour la réduction de dimension. PySpark's MLlib offre une implémentation distribuée de PCA, ce qui la rend adaptée aux grands ensembles de données. PCA transforme les données en un nouveau système de coordonnées où les premières dimensions (composantes principales) capturent la variance maximale des données.

### Détails de l'implémentation

Le script utilise la classe `PCA` du module `pyspark.ml.feature`. Il est important que la colonne d'entrée pour PCA soit de type `VectorUDT`, qui est le format de vecteur dense ou creux utilisé par MLlib. Si vos caractéristiques sont sous forme de liste Python (comme c'est le cas après la featurisation avec l'UDF), une conversion en `Vectors.dense` est nécessaire.

Le paramètre `k` dans l'initialisation de `PCA` spécifie le nombre de composantes principales à conserver. Le modèle PCA est d'abord `fit` (entraîné) sur le DataFrame d'entrée, puis `transform` (appliqué) pour obtenir le DataFrame avec les caractéristiques réduites.

```python
from pyspark.ml.feature import PCA
from pyspark.ml.linalg import Vectors, VectorUDT
from pyspark.sql.types import StructType, StructField

# Supposons que df_features est le DataFrame obtenu après la featurisation,
# et qu\'il contient une colonne \'features\' de type ArrayType(FloatType())

# Convertir la colonne \'features\' en VectorUDT, nécessaire pour PCA
# Si votre colonne \'features\' est déjà un VectorUDT, cette étape n\'est pas nécessaire.
# Assurez-vous que la colonne \'features\' est de type VectorUDT pour PCA.
# Exemple de conversion si \'features\' est un ArrayType(FloatType()):
# from pyspark.sql.functions import udf
# list_to_vector_udf = udf(lambda l: Vectors.dense(l), VectorUDT())
# df_features_vector = df_features.withColumn("features_vector", list_to_vector_udf(df_features["features"]))

# Pour cet exemple, nous allons créer un DataFrame de démonstration
# avec une colonne \'features_vector\' de type VectorUDT
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
```


