"""The product logic, pure: data in, data out. No FastAPI, HTTP client, SDK or env reads here.

tests/test_architecture.py fails if a module here imports api, adapters, settings, or a web or LLM
library. Outside services come in as arguments: declare what you need as a typing.Protocol here.
"""
