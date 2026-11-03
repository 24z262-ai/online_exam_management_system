pipeline {
    agent any
    environment {
        IMAGE_NAME = 'online-exam'
        SONARQUBE_ENV = 'SonarQube'
    }
    stages {
        stage('Checkout') { steps { checkout scm } }
        stage('Install dependencies') {
            steps { sh 'python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt' }
        }
        stage('Tests') {
            steps { sh '. .venv/bin/activate && pytest -v' }
        }
        stage('SonarQube analysis') {
            when { expression { return env.SONAR_TOKEN?.trim() } }
            steps {
                withSonarQubeEnv(SONARQUBE_ENV) {
                    sh 'sonar-scanner -Dsonar.login=$SONAR_TOKEN'
                }
            }
        }
        stage('Docker build') {
            steps { sh 'docker build -t ${IMAGE_NAME}:${BUILD_NUMBER} -t ${IMAGE_NAME}:latest .' }
        }
        stage('Deploy') {
            when { branch 'main' }
            steps {
                sh '''docker rm -f online-exam || true
                docker run -d --restart unless-stopped --name online-exam -p 5000:5000 \\
                  -e MYSQL_HOST="$MYSQL_HOST" -e MYSQL_USER="$MYSQL_USER" \\
                  -e MYSQL_PASSWORD="$MYSQL_PASSWORD" -e MYSQL_DATABASE="$MYSQL_DATABASE" \\
                  -e SECRET_KEY="$SECRET_KEY" -e ADMIN_EMAIL="$ADMIN_EMAIL" \\
                  -e ADMIN_PASSWORD="$ADMIN_PASSWORD" ${IMAGE_NAME}:${BUILD_NUMBER} \\
                  sh -c 'flask --app app init-db && exec gunicorn --bind 0.0.0.0:5000 --workers 2 app:app' '''
            }
        }
    }
}
