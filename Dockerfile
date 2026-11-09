# MediBuddy-Bench, reproducible image.
#   build:  docker build -t medibuddy-bench .
#   serve the benchmark (A2A service on :9009):      docker run --rm -p 9009:9009 medibuddy-bench
#   score a built-in agent, no network needed:       docker run --rm medibuddy-bench run --agent oracle --data data/lite
#   check the install:                               docker run --rm medibuddy-bench doctor
#   hidden split (organiser only):                   docker run --rm -p 9009:9009 -v /private/test:/test medibuddy-bench serve --data /test
# Dependencies are pinned in requirements-a2a.lock (the exact versions the tests ran with); the image adds nothing else.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements-a2a.lock ./
RUN pip install -r requirements-a2a.lock

COPY medibuddy_bench ./medibuddy_bench
COPY scripts ./scripts
COPY configs ./configs
COPY examples ./examples
COPY data/lite ./data/lite
COPY data/dev ./data/dev

# Fail the build if the baked-in data is corrupted or differs from its manifest.
RUN python -m medibuddy_bench verify --data data/lite && python -m medibuddy_bench verify --data data/dev

EXPOSE 9009
ENTRYPOINT ["python", "-m", "medibuddy_bench"]
CMD ["serve", "--host", "0.0.0.0", "--port", "9009"]
