# Instructions d'installation et d'exécution du Notebook PySpark sur AWS EMR

Ce document fournit des instructions détaillées et pas à pas pour déployer et exécuter votre script PySpark sur un cluster Amazon EMR (Elastic MapReduce). Il couvre la configuration du cluster, la gestion des données sur S3, la connexion au notebook et l'exécution du script, tout en tenant compte des contraintes de coût et de conformité RGPD.

## Prérequis

Avant de commencer, assurez-vous d'avoir les éléments suivants :

1.  **Un compte AWS actif** avec les permissions nécessaires pour créer des clusters EMR, des buckets S3 et des rôles IAM.
2.  **Le jeu de données `fruits.zip`** téléchargé localement.
3.  **Le script PySpark (`pyspark_script.py`)** que nous avons développé, contenant la logique de featurisation et de PCA.
4.  **Une paire de clés SSH** (`.pem` file) pour se connecter au nœud maître EMR. Si vous n'en avez pas, vous pouvez en créer une via la console EC2.

## 1. Configuration d'Amazon S3

Amazon S3 (Simple Storage Service) est un service de stockage d'objets qui sera utilisé pour stocker vos données d'entrée (images de fruits) et les résultats de vos traitements PySpark. Il est hautement disponible, durable et scalable.

### 1.1 Création des buckets S3

Pour des raisons de conformité RGPD, nous allons créer nos buckets dans une région européenne (par exemple, `eu-west-1` - Irlande ou `eu-central-1` - Francfort).

1.  Connectez-vous à la **Console de gestion AWS**.
2.  Naviguez vers le service **S3**.
3.  Cliquez sur **Créer un bucket**.
4.  **Nom du bucket** : Choisissez un nom unique et descriptif (ex: `mon-projet-fruits-input-data-unique-id`).
5.  **Région AWS** : Sélectionnez une région européenne (ex: `Europe (Irlande) eu-west-1`).
6.  Laissez les autres options par défaut pour le moment (vous pouvez ajuster les paramètres de blocage de l'accès public si nécessaire, mais pour un usage personnel, les paramètres par défaut sont souvent suffisants).
7.  Cliquez sur **Créer un bucket**.
8.  Répétez les étapes 3 à 7 pour créer un deuxième bucket pour les résultats (ex: `mon-projet-fruits-output-data-unique-id`).

### 1.2 Téléchargement des données sur S3

Maintenant, nous allons télécharger le jeu de données `fruits.zip` dans votre bucket d'entrée.

1.  Dans la console S3, cliquez sur le bucket que vous avez créé pour les données d'entrée (ex: `mon-projet-fruits-input-data-unique-id`).
2.  Cliquez sur **Télécharger**.
3.  Cliquez sur **Ajouter des fichiers** et sélectionnez votre fichier `fruits.zip`.
4.  Cliquez sur **Télécharger**.

Une fois le fichier `fruits.zip` téléchargé, vous devrez le décompresser sur S3. Pour les fichiers volumineux, il est souvent plus efficace de décompresser directement sur le cluster EMR ou d'utiliser AWS Glue/Lambda pour la décompression si le volume est très important. Pour ce projet, nous considérerons que les images seront accessibles directement ou décompressées lors du traitement sur EMR.

## 2. Lancement d'un cluster Amazon EMR

Amazon EMR est un service géré qui facilite l'exécution de frameworks Big Data comme Apache Spark, Hadoop, Hive, et Presto sur AWS. Nous allons configurer un cluster pour exécuter notre script PySpark.

### 2.1 Création du cluster EMR

1.  Dans la console de gestion AWS, naviguez vers le service **EMR**.
2.  Cliquez sur **Créer un cluster**.
3.  **Configuration rapide ou Paramètres avancés** : Choisissez **Paramètres avancés** pour un contrôle plus fin.

### 2.2 Étape 1 : Logiciels et étapes

1.  **Version du logiciel** : Sélectionnez la dernière version stable d'EMR (ex: `emr-6.x.x`).
2.  **Applications** : Sélectionnez au minimum `Spark` et `Hadoop`. Vous pouvez également ajouter `JupyterHub` ou `JupyterEnterpriseGateway` si vous prévoyez d'utiliser un notebook directement sur le cluster.
3.  **Modifier les paramètres du logiciel** : Vous pouvez laisser les paramètres par défaut pour commencer. Si vous avez besoin de configurations Spark spécifiques (mémoire, cœurs), vous pouvez les ajouter ici (ex: `spark.executor.memory=4g`).
4.  **Étapes** : Pour ce projet, nous n'ajouterons pas d'étapes de démarrage ici, nous exécuterons le script manuellement via SSH/Jupyter.

### 2.3 Étape 2 : Matériel

1.  **Type d'instance de nœud principal** : Choisissez un type d'instance approprié (ex: `m5.xlarge` ou `m5.2xlarge` pour le nœud maître). Le nœud maître gère le cluster et exécute le pilote Spark.
2.  **Type d'instance de nœud de cœur** : Choisissez un type d'instance pour les nœuds de données et de calcul (ex: `m5.xlarge`). Définissez le **Nombre d'instances** (ex: 2 ou 3 pour commencer). Ces nœuds exécuteront les tâches Spark.
3.  **Type d'instance de nœud de tâche** : Vous pouvez en ajouter si vous avez besoin de capacité de calcul supplémentaire sans stockage de données persistant.

### 2.4 Étape 3 : Paramètres de cluster généraux

1.  **Nom du cluster** : Donnez un nom significatif à votre cluster (ex: `MonClusterFruits`).
2.  **Dossier de journalisation S3** : Spécifiez un chemin S3 pour les journaux du cluster (ex: `s3://mon-projet-fruits-output-data-unique-id/logs/`).
3.  **Paire de clés EC2** : Sélectionnez la paire de clés SSH que vous avez créée ou importée précédemment. C'est essentiel pour se connecter au nœud maître.
4.  **Actions d'amorçage (Bootstrap Actions)** : C'est ici que nous allons installer les bibliothèques Python nécessaires (TensorFlow, Pillow, etc.) sur tous les nœuds du cluster. Ajoutez une nouvelle action d'amorçage avec les détails suivants :
    *   **Nom** : `Install Python Libraries`
    *   **Script S3** : Laissez vide pour un script personnalisé.
    *   **Arguments** : Collez le script suivant. Ce script installera les paquets Python nécessaires via `pip`.

    ```bash
    #!/bin/bash
    sudo pip3 install tensorflow==2.5.0 pillow pandas pyspark==3.1.2 pyarrow
    ```
    *Note: Les versions des paquets doivent correspondre à celles utilisées dans votre environnement local et compatibles avec la version de Python sur EMR.* 

### 2.5 Étape 4 : Sécurité

1.  **Rôle de service EMR** : Laissez le rôle par défaut (`EMR_DefaultRole`) ou créez-en un nouveau avec les permissions nécessaires (accès S3, EC2, etc.).
2.  **Rôle de profil d'instance EC2** : Laissez le rôle par défaut (`EMR_EC2_DefaultRole`).
3.  **Groupes de sécurité** : Il est recommandé de créer des groupes de sécurité personnalisés pour le nœud maître et les nœuds de cœur/tâche. Assurez-vous que le groupe de sécurité du nœud maître autorise les connexions SSH (port 22) depuis votre adresse IP.

### 2.6 Lancement du cluster

Cliquez sur **Créer un cluster**. Le lancement du cluster peut prendre plusieurs minutes. Vous pouvez suivre son état dans la console EMR.

## 3. Connexion au cluster EMR et exécution du script PySpark

Une fois le cluster en état `Waiting` (ou `Running`), vous pouvez vous y connecter.

### 3.1 Connexion SSH au nœud maître

1.  Dans la console EMR, cliquez sur le nom de votre cluster.
2.  Dans l'onglet **Résumé**, recherchez l'**Adresse IP publique DNS** du nœud maître.
3.  Ouvrez un terminal sur votre machine locale.
4.  Utilisez la commande SSH pour vous connecter, en utilisant votre paire de clés (`.pem`) :

    ```bash
    ssh -i /chemin/vers/votre/cle.pem hadoop@<Adresse_IP_publique_DNS_du_maître>
    ```
    Remplacez `/chemin/vers/votre/cle.pem` par le chemin réel de votre fichier de clé et `<Adresse_IP_publique_DNS_du_maître>` par l'adresse IP de votre nœud maître.

### 3.2 Transfert du script PySpark

Une fois connecté en SSH, vous pouvez transférer votre script `pyspark_script.py` vers le nœud maître. Vous pouvez le faire via `scp` depuis votre machine locale avant de vous connecter en SSH, ou utiliser `wget`/`curl` si le script est hébergé quelque part.

Depuis votre machine locale (dans un nouveau terminal) :

```bash
scp -i /chemin/vers/votre/cle.pem /chemin/vers/pyspark_script.py hadoop@<Adresse_IP_publique_DNS_du_maître>:/home/hadoop/
```

### 3.3 Exécution du script PySpark

Sur le nœud maître EMR (dans votre session SSH) :

1.  Assurez-vous que votre script est dans le répertoire `/home/hadoop/`.
2.  Exécutez le script PySpark en utilisant `spark-submit` :

    ```bash
    spark-submit --master yarn --deploy-mode client /home/hadoop/pyspark_script.py
    ```
    *Note: Adaptez les chemins S3 dans votre script PySpark pour qu'ils pointent vers vos buckets (ex: `s3://mon-projet-fruits-input-data-unique-id/fruits.zip`).*

    Si votre script nécessite des ressources spécifiques ou des arguments, vous pouvez les ajouter à la commande `spark-submit`.

### 3.4 Accès à JupyterHub/JupyterLab (Optionnel)

Si vous avez installé JupyterHub/JupyterEnterpriseGateway sur votre cluster EMR, vous pouvez y accéder via un tunnel SSH.

1.  Depuis votre machine locale, ouvrez un tunnel SSH :

    ```bash
    ssh -i /chemin/vers/votre/cle.pem -N -L 8888:<Adresse_IP_privée_du_maître>:8888 hadoop@<Adresse_IP_publique_DNS_du_maître>
    ```
    Remplacez `<Adresse_IP_privée_du_maître>` par l'adresse IP privée du nœud maître (disponible dans la console EMR).
2.  Ouvrez votre navigateur web et accédez à `http://localhost:8888`.
3.  Vous devriez être redirigé vers l'interface JupyterHub/JupyterLab de votre cluster EMR, où vous pourrez télécharger et exécuter votre notebook (`.ipynb`).

## 4. Gestion des coûts : Résiliation du cluster EMR

**Très important :** Les clusters EMR entraînent des coûts tant qu'ils sont en cours d'exécution. Pour éviter des frais inutiles, **résiliez toujours votre cluster EMR après avoir terminé vos tests ou démonstrations.**

1.  Dans la console EMR, sélectionnez votre cluster.
2.  Cliquez sur **Terminer**.
3.  Confirmez la résiliation.

En suivant ces étapes, vous pourrez déployer et exécuter votre projet PySpark sur AWS EMR de manière efficace et économique.


