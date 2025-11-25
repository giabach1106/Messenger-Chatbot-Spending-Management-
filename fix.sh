docker rm -f $(docker ps -a -q)
docker volume prune -f
docker-compose up -d --build
docker-compose logs -f --tail=50 backend