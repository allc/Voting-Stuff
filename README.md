# compsoc committee sso framework

## what?

This is a template project to demonstrate allowing compsoc committee members to sign into internal applications, using our existing google admin platform.
It also ships with a *highly opinionated* Flask framework, for easily building and deploying new CompSoc microservices, through some makefile abuse.

This template ships with:

 - [Flask](//palletsprojects.com/p/flask/)
 - [Bulma](//bulma.io)
 - [SQLite](https://www.sqlite.org/index.html)
 - [socket.io](//socket.io) *(experimental)*

## why?

This lets us greatly reduce the overhead of launching new applications, as we can shift account management up to the long-suffering administrator.

## how?

This is just a demo application, intended as a starting off point for creating new applications. You'll need to create a project on (ideally CompSoc's) [GCP](https://console.cloud.google.com/), issue a client ID and secret for a web oauth application, and properly configure the callback urls.

More verbosely:

1) Log into [GCP](https://console.cloud.google.com), and create a new project by clicking the project header on the title bar and clicking "New Project." Ideally this should be created under the "comp-soc.com" domain.

2) Once you've created the project, go to the sidebar > APIs & Services > Credentials. You should mark it as an internal service, given the option (Google seems to keep changing this). You'll need to add routes like so:

![credentials](/docs/credentials.png?raw=true)
![routes](/docs/routes.png?raw=true)

Here are the authorized javascript origins so you can copy/paste them:

```
https://your-service.comp-soc.com
http://localhost:5000
http://127.0.0.1:5000
```

And similarly for the authorized redirect URIs:

```
https://your-service.comp-soc.com/login/google/authorized
http://localhost:5000/login/google/authorized
http://127.0.0.1:5000/login/google/authorized
```

3) You'll also need to enable access to the People API, which is used to retrieve a profile photo and other information. This can be done through the sidebar > APIs & Services > Library portal.

Once you've done that, you'll need to create your json configuration file in `instance/secret.json`:

```json
{
    "client_id": "YOUR_GOOGLE_CLIENT_ID",
    "client_secret": "YOUR_GOOGLE_CLIENT_SECRET",
    "app_secret_key": "SOME_RANDOM_STRING"
}
```

Initialize the virtual environment for the project:

```
$ make init-venv
```


Then you should be good to go! Start the server with:

```
$ make run
```

### deploying?

Deploying the application is slightly more involved than just running it, but it's not horrendously complicated either.

First, you'll need to look inside of `./makefile`, and tweak the variables at the top to point at your server.

Next, you'll need to edit the `./docker-compose.yml`. Similar to before, just make sure everything in there looks right (you will likely need to change the image name).

To actually deploy your application, you will need to first initialize the deployment folder on the remote:

```
$ make init-deploy
```

To build and upload the project:

```
$ make deploy
```

Finally, you'll need to hook up a reverse proxy webserver. I recommend NGINX, and have provided a default configuration in `docs/compsoc-sso.nginx.conf`.
Copy that to `/etc/nginx/sites-available`, and then enable the vhost by running:

```
$ sudo ln -s /etc/nginx/sites-available/compsoc-sso.nginx.conf /etc/nginx/sites-enabled/compsoc-sso.nginx.conf
```

Obtain a certificate for free (thanks [Let's Encrpyt](//letsencrypt.org)!) by running:

```
$ sudo certbot
```

## make?

That's right, this absolutely abuses make.

Make commands available are:

command | stage | effect
---|---|---
`init-venv` | *dev* | create a virtual environment
`run` | *dev* | __start the local dev server__
`init-db` | *dev* | clear and initialize the database by running `app/schema.sql`
`clean` | *deploy* | clean up the last build if necessary
`build` | *deploy* | build the docker image
`upload` | *deploy* | upload the image to the server
`init-deploy` | *deploy* | prepare the server to receive deployments
`connect` | *maintain* | connect to the server for convenience

## who?

This was written in a fit of procrastination by [@pkage](//kage.dev).
