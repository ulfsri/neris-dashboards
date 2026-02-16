This setup segregates dashboards `apps/` from shared libraries `libs/` in a way that allows both
1. local work with dependency on live-editable the libraries. To run with hot reloading across your app and a library:

```
uv run --package cornsacks python apps/cornsacks/app.py
```

2. Automated packaging, requirements-gathering, and CLI deployment with

```
scripts/deploy-dash-enterprise.sh apps/cornsacks cornsacks
```
