"""The backend, as ports and adapters (docs/decisions/0005-pipeline-core.md).

core: the drawing model, the ingest stages and answering, pure, with their ports as Protocols.
adapters: implement the ports. composition: picks an adapter per port from the settings.
Entry points: cli (now) and api (HTTP) call the use cases through composition.
"""
