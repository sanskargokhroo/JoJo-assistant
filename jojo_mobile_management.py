"""Authenticated companion settings; credential values are write-only."""
from fastapi import Request, HTTPException
from pydantic import BaseModel, Field


class ModelSetup(BaseModel):
    provider: str = Field(max_length=30)
    model: str = Field(min_length=1, max_length=150)
    api_key: str = Field(min_length=1, max_length=500)


def register(app, authenticate):
    @app.get('/api/mobile/management')
    def status(request: Request):
        authenticate(request)
        from jojo_config import PROVIDER, MODEL, api_keys, read_preferences
        from jojo_capabilities import catalog
        from jojo_user_config import load
        account=load()
        return {'provider':PROVIDER,'model':MODEL,'key_configured':bool(api_keys()),
                'saved_provider':account.get('provider',''),'saved_model':account.get('model',''),
                'remember_tasks':read_preferences().get('remember_tasks',True),
                'skills':catalog()}

    @app.post('/api/mobile/management/skills')
    def skills(values: dict, request: Request):
        authenticate(request)
        from jojo_capabilities import update
        # A phone cannot disconnect its own management channel or toggle laptop control.
        if set(values) & {'mobile','desktop'}:
            raise HTTPException(400,'Manage device control from PC Skills.')
        try:update(values)
        except ValueError as exc:raise HTTPException(400,str(exc))
        return {'message':'Skills saved.'}

    @app.post('/api/mobile/management/memory')
    def memory(values: dict, request: Request):
        authenticate(request)
        if set(values)!={'remember_tasks'} or type(values['remember_tasks']) is not bool:
            raise HTTPException(400,'Invalid memory setting')
        from jojo_config import save_preferences
        save_preferences(values)
        return {'message':'Task memory setting saved for both devices. Existing memory is retained.'}

    @app.post('/api/mobile/management/model')
    def model(values: ModelSetup, request: Request):
        authenticate(request)
        from jojo_user_config import load, private_dir, protect
        import base64,json
        if values.provider not in {'gemini','openai','anthropic'}:
            raise HTTPException(400,'Unsupported provider')
        current=load()
        secret={'api_key':values.api_key.strip()}
        if not secret['api_key'] or not values.model.strip():raise HTTPException(400,'Model and key are required')
        if current.get('firebase'):secret['firebase']=current['firebase']
        current={k:v for k,v in current.items() if k not in {'api_key','firebase','secrets'}}
        current.update(provider=values.provider,model=values.model.strip(),secrets=base64.b64encode(protect(json.dumps(secret).encode())).decode())
        path=private_dir()/'jojo_account.json';temporary=path.with_suffix('.tmp')
        temporary.write_text(json.dumps(current),encoding='utf-8');temporary.replace(path)
        return {'message':'Key encrypted and saved. Restart the laptop backend to apply. Existing environment overrides take priority; check active model after restart.'}
