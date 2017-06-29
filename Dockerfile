FROM fedoraqa/flask-base:24

COPY . /usr/src/resultsdb
WORKDIR /usr/src/resultsdb
EXPOSE 5001
ENV DEV true
RUN pip install -r requirements.txt &&\
    python run_cli.py init_db

CMD ["python", "runapp.py"]
