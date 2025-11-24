docker rm -f $(docker ps -a -q)
docker volume prune -f
docker-compose up -d --build
