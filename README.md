# chore_chart
Simple chore charts for kids

## docker build:
docker build -t chore-chart-app .

## docker run:
docker run -p 5000:5000 -e ADMIN_PASSWORD="your_strong_password" -v "$(pwd)/db_data:/app" chore-chart-app
