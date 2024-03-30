VIRTUALENV = env_ccauth
DOCKER_TAG_NAME = compsoc-sso-demo
REMOTE = compsoc-admin@bucket.comp-soc.com
REMOTE_DESTINATION = ~/sso-demo
STAGING = staging

all: run

run:
	source ${VIRTUALENV}/bin/activate && \
		OAUTHLIB_INSECURE_TRANSPORT=1    \
		OAUTHLIB_RELAX_TOKEN_SCOPE=1     \
		FLASK_DEBUG=1	                 \
		FLASK_ENVIRONMENT=development    \
		python -m flask run

init-db:
	source ${VIRTUALENV}/bin/activate && \
		FLASK_DEBUG=0                    \
		FLASK_ENVIRONMENT=development    \
		python -m flask init-db

clean:
	rm -f ${STAGING}/${DOCKER_TAG_NAME}.tar.gz

build: clean
	mkdir -p ${STAGING}
	docker build . -t ${DOCKER_TAG_NAME}
	docker save ${DOCKER_TAG_NAME} -o ${STAGING}/${DOCKER_TAG_NAME}.tar.gz

upload: build
	scp ${STAGING}/${DOCKER_TAG_NAME}.tar.gz ${REMOTE}:${REMOTE_DESTINATION}/${DOCKER_TAG_NAME}.tar.gz

connect:
	ssh ${REMOTE}

deploy: upload
	ssh -t ${REMOTE} 'cd ${REMOTE_DESTINATION}; sudo docker-compose stop; sudo docker load -i ${DOCKER_TAG_NAME}.tar.gz; sudo docker-compose up -d;'


init-deploy:
	ssh -t ${REMOTE} 'mkdir -p ${REMOTE_DESTINATION}'
	scp docker-compose.yml ${REMOTE}:${REMOTE_DESTINATION}
	scp -r instance ${REMOTE}:${REMOTE_DESTINATION}

init-venv:
	virtualenv ${VIRTUALENV} -p python3
	source ${VIRTUALENV}/bin/activate && \
		python -m pip install -r requirements.txt --verbose

