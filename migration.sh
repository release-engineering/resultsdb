git commit -am .
docker stop pg_resultsdb;docker rm pg_resultsdb;docker run --name pg_resultsdb -e POSTGRES_USER=resultsdb -e POSTGRES_PASSWORD=fedora -p 5432:5432 -d postgres
sleep 10
git co 5dc67d8382dd0c0aaf5b9d74df4dd2c00585af4e; DEV=true bash init_db.sh; git co feature/v20
DEV=true alembic upgrade 540dbe71fa91


#DEV=true alembic upgrade head
