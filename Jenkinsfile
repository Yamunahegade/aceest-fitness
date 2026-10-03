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
                // Pulls the latest code from GitHub (configured in the Jenkins job)
                checkout scm
            }
        }

        stage('Clean Build Environment') {
            steps {
                sh 'docker rmi -f ${IMAGE_NAME}:${BUILD_NUMBER} ${IMAGE_NAME}-test:${BUILD_NUMBER} || true'
            }
        }

        stage('Build Docker Image') {
            steps {
                sh 'docker build --no-cache -t ${IMAGE_NAME}:${BUILD_NUMBER} .'
            }
        }

        stage('Quality Gate: Pytest') {
            steps {
                sh 'docker build -f Dockerfile.test -t ${IMAGE_NAME}-test:${BUILD_NUMBER} .'
                sh 'docker run --rm ${IMAGE_NAME}-test:${BUILD_NUMBER}'
            }
        }
    }

    post {
        success { echo 'BUILD SUCCESS: image built and all tests passed.' }
        failure { echo 'BUILD FAILED: check the console output above.' }
        always  { sh 'docker image prune -f || true' }
    }
}
