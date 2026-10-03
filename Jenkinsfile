pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
    }

    environment {
        IMAGE_NAME = 'aceest-fitness'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Install Dependencies') {
            steps {
                sh '''
                    python3 -m venv .venv
                    . .venv/bin/activate
                    pip install --quiet -r requirements-dev.txt
                '''
            }
        }

        stage('Lint') {
            steps {
                sh '. .venv/bin/activate && flake8 .'
            }
        }

        stage('Quality Gate: Pytest') {
            steps {
                sh '. .venv/bin/activate && pytest -v'
            }
        }

        stage('Docker Build and Test') {
            // Runs only when this Jenkins agent is allowed to use Docker
            when {
                expression { sh(returnStatus: true, script: 'docker info > /dev/null 2>&1') == 0 }
            }
            steps {
                sh 'docker build --no-cache -t ${IMAGE_NAME}:${BUILD_NUMBER} .'
                sh 'docker build -f Dockerfile.test -t ${IMAGE_NAME}-test:${BUILD_NUMBER} .'
                sh 'docker run --rm ${IMAGE_NAME}-test:${BUILD_NUMBER}'
            }
        }
    }

    post {
        success { echo 'BUILD SUCCESS: lint and all tests passed.' }
        failure { echo 'BUILD FAILED: check the console output above.' }
    }
}
