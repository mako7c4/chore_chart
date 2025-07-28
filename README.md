# chore chart
Simple chore charts for kids

## docker build:
docker build -t chore-chart-app .

## Generate SECRET_KEY
python3
import secrets
secrets.token_hex(24)
#copy output to SECRET_KEY for startup

## docker run:
docker run --name chart -p 5000:5000 -e SECRET_KEY="a_super_long_and_random_secret_string" -v "$(pwd)/db_data:/app/data" chore-chart-app

## Default page 
![image](https://github.com/user-attachments/assets/9f0b6567-d8ee-4f25-a70d-a98f4e1ff2cf)

## Admin interface/configuration
![image](https://github.com/user-attachments/assets/afb6f7a1-6fe4-4cbe-bbc9-7ee85ecbe91a)

