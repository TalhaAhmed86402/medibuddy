# Green agent (the benchmark service).  Build:  docker build -t medibuddy-bench .
# Run:    docker run -p 9009:9009 medibuddy-bench           (dev split baked in)
# Hidden test split: mount it and pass --data:  -v /private/test:/test  ...  --data /test
FROM python:3.12-slim
WORKDIR /app
COPY requirements-a2a.txt .
RUN pip install --no-cache-dir -r requirements-a2a.txt
COPY medibuddy_bench ./medibuddy_bench
COPY data/dev ./data/dev
COPY data/lite ./data/lite
EXPOSE 9009
ENTRYPOINT ["python", "-m", "medibuddy_bench.a2a.green_server", "--host", "0.0.0.0", "--port", "9009"]
