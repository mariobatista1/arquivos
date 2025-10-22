depois de sobrescrever os arquivos rodar:
npm install na pasta frontend e backend

comando pra subir os containers no docker:
docker-compose up --build

frontend roda fora do docker, depois de subir os containers no docker roda:
npm run dev

entra no banco e cria uma query na tabela gateway_config e roda esse comando:
ALTER TABLE gateway_config ADD COLUMN webhook_secret varchar(255);

cria primeiro o banco no pgadmin e depois sobe o dump

conexão pgadmin docker:
Host name/address => playercore-postgres ✅
Port => 5432
Maintenance database => playercore_retain
Username => postgres
Password => playercore123

comando para adicionar o dump no banco do docker:
docker exec -i playercore-postgres psql -U postgres -d playercore_retain -f /user/exemplo/Downloads/dump.sql
