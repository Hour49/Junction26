"""The product logic, pure: data in, data out. No FastAPI, HTTP client, SDK or env reads here.

drawing/ is the drawing model, pipeline/ the ingest stages, answering/ the question side. What
they need from outside is a typing.Protocol in their ports.py, passed in as an argument.
tests/test_architecture.py fails if a module here imports api, adapters, settings, composition,
the CLI, or a web, LLM, PDF or image library.
"""
