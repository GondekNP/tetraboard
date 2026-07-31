FROM python:3.12-slim

WORKDIR /workspace

# Only tooling lives in the container. The actual sketch runs client-side
# in your host browser via Pyodide/PyScript, so no GUI/X11 forwarding,
# pygame, or SDL setup is needed here at all.
COPY . .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements-dev.txt

RUN apt update -y
RUN apt install make git gh -y

EXPOSE 8000
