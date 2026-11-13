"""One module per outside service (LLM, partner API), each with its fake. Empty until the first one.

Adding one (docs/ENGINEERING.md section 1): `<service>.py` holds the client class (the only SDK
import, key from Settings, timeouts) and a `Fake<Service>` with recorded responses. A
`get_<service>(request)` provider builds the client from `request.app.state.settings`; routes take
`Annotated[<Service>, Depends(get_<service>)]`; tests set
`app.dependency_overrides[get_<service>] = lambda: Fake<Service>()`.
"""
