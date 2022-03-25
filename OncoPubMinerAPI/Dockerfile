FROM python:3.6
MAINTAINER "lyy"
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
EXPOSE 9001
ENTRYPOINT ["python"]
CMD ["app/manage.py"]
