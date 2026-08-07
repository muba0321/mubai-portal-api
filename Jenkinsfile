// Jenkinsfile - SRE Portal 后端 CI/CD
// 手动触发，部署到 154.201.73.215

pipeline {
    agent { label 'deploy-agent' }  // 215 上的 Jenkins Agent

    environment {
        GIT_REPO = 'https://github.com/muba0321/mubai-portal-api.git'
        GIT_BRANCH = 'main'
        DEPLOY_HOST = '154.201.73.215'
        DEPLOY_USER = 'root'
        APP_DIR = '/opt/sre-portal'
        CONTAINER_NAME = 'sre-portal-backend'
    }

    stages {
        stage('Checkout') {
            steps {
                echo '=== 拉取代码 ==='
                git branch: GIT_BRANCH, url: GIT_REPO
            }
        }

        stage('Build Image') {
            steps {
                echo '=== 构建 Docker 镜像 ==='
                sh '''
                    cd ${APP_DIR}/workspace/sre-portal-backend
                    docker build -t sre-portal-backend:latest .
                '''
            }
        }

        stage('Deploy') {
            steps {
                echo '=== 部署后端 ==='
                sh '''
                    cd ${APP_DIR}
                    docker compose up -d --build sre-portal-backend
                    sleep 5
                    # 健康检查
                    for i in $(seq 1 10); do
                        if curl -sf http://localhost:5000/health > /dev/null; then
                            echo "Backend healthy!"
                            exit 0
                        fi
                        echo "Waiting... ($i/10)"
                        sleep 3
                    done
                    echo "Backend health check failed!"
                    exit 1
                '''
            }
        }

        stage('Verify') {
            steps {
                echo '=== 验证部署 ==='
                sh '''
                    curl -sf http://localhost:5000/health | python3 -m json.tool
                    docker ps | grep ${CONTAINER_NAME}
                '''
            }
        }
    }

    post {
        success {
            echo '✅ 后端部署成功'
        }
        failure {
            echo '❌ 后端部署失败'
        }
    }
}
