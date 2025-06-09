## Mission - Réalisez un traitement dans un environnement Big Data sur le Cloud

Cette mission suit un scénario de projet professionnel.

Vous êtes Data Scientist dans une très jeune start-up de l'AgriTech, nommée "**Fruits!**", qui cherche à proposer des solutions innovantes pour la récolte des fruits.

La volonté de l’entreprise est de préserver la biodiversité des fruits en permettant des traitements spécifiques pour chaque espèce de fruits en développant des robots cueilleurs intelligents.

Votre start-up souhaite dans un premier temps se faire connaître en mettant à disposition du grand public une application mobile qui permettrait aux utilisateurs de prendre en photo un fruit et d'obtenir des informations sur ce fruit.

Pour la start-up, cette application permettrait de sensibiliser le grand public à la biodiversité des fruits et de mettre en place une première version du moteur de classification des images de fruits.

De plus, le développement de l’application mobile permettra de construire une première version de l'architecture Big Data nécessaire.

Votre collègue Paul vous indique l’existence d’un document, formalisé par un alternant qui vient de quitter l’entreprise. Il a testé une première approche dans un environnement Big Data AWS EMR, à partir d’un [jeu de données](https://www.kaggle.com/moltean/fruits) constitué des images de fruits et des labels associés (en téléchargement direct à [ce lien](https://s3.eu-west-1.amazonaws.com/course.oc-static.com/projects/Data_Scientist_P8/fruits.zip)). Le notebook réalisé par l’alternant (P8_Notebook_Linux_EMR_PySpark_V1.0.ipynb) servira de point de départ pour construire une partie de la chaîne de traitement des données.

Vous êtes donc chargé de vous approprier les travaux réalisés par l’alternant et de compléter la chaîne de traitement. Il n’est pas nécessaire d’entraîner un modèle pour le moment. L’important est de mettre en place les premières briques de traitement qui serviront lorsqu’il faudra passer à l’échelle en termes de volume de données !

Lors de son brief initial, Paul vous a averti des points suivants :

- Vous devrez tenir compte dans vos développements du fait que le volume de données va augmenter très rapidement après la livraison de ce projet. Vous continuerez donc à développer des scripts en Pyspark et à utiliser le cloud AWS pour profiter d’une architecture Big Data (EMR, S3, IAM). Si vous préférez, vous pourrez transférer les traitements dans un environnement Databricks.
- Vous devez faire une démonstration de la mise en place d’une instance EMR opérationnelle, ainsi qu’ expliquer pas à pas le script PySpark, que vous aurez complété :

- d’un traitement de diffusion des poids du modèle Tensorflow sur les clusters (broadcast des “weights” du modèle) qui avait été oublié par l’alternant. Vous pourrez vous appuyer sur l’article “Model inference using TensorFlow Keras API (en anglais)” disponible dans les ressources.
- d’une étape de réduction de dimension de type PCA en PySpark.

- Vous respecterez les contraintes du RGPD : dans notre contexte, vous veillerez à paramétrer votre installation afin d’utiliser des serveurs situés sur le territoire européen.
- Votre retour critique de cette solution sera également précieuse, avant de décider de la généraliser.
- La mise en œuvre d’une architecture Big Data de type EMR engendrera des coûts. Vous veillerez donc à ne maintenir l’instance EMR opérationnelle que pour les tests et les démos.

Ce coût, qui devrait rester inférieur à 10 euros pour une utilisation raisonnée, reste à votre charge. L’utilisation d’un serveur local pour la mise à jour du Script PySpark, en limitant l’utilisation du serveur EMR à l’implémentation et aux tests, permet de réduire sensiblement ce coût.

### Étapes

###

#### Étape 1 : Préparez la chaîne de traitement PySpark en local

- Reprenez le notebook de l'alternant et complétez la démarche, notamment avec une étape de réduction de dimension en PySpark.

###

#### Étape 2 : Migrez votre chaîne de traitement dans le Cloud (en utilisant AWS, par exemple)

- Prenez connaissance des services AWS et identifiez les services pertinents pour migrer chaque étape de votre chaîne de traitement en local.
- Mettez en place le cluster EMR pour distribuer les calculs dans le cloud et connectez-y votre notebook Cloud pour réaliser la chaîne de traitement jusqu’à la réduction de dimensions.

###

#### Étape 3 : Vérifiez votre travail et preparez-vous à la soutenance

- Vérifiez que votre notebook PySpark est clair et les scripts bien commentés pour une démonstration efficace. Assurez-vous que les données et résultats sont organisés et accessibles dans le Cloud.
- Préparez une présentation concise expliquant votre architecture cloud et le processus de traitement PySpark, en soulignant les choix technologiques.
- Pratiquez la présentation pour garantir une explication fluide et une démonstration technique sans accroc, tout en étant prêt pour la discussion technique avec l'évaluateur.
