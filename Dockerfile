FROM python:3.13

RUN apt update
RUN pip install --upgrade pip
RUN pip install poetry