def register_blueprints(app):
    from app.routes.attendance_routes import attendance_bp
    from app.routes.auth_routes import auth_bp
    from app.routes.dashboard_routes import dashboard_bp
    from app.routes.document_routes import document_bp
    from app.routes.employee_routes import employee_bp
    from app.routes.leave_routes import leave_bp
    from app.routes.onboarding_routes import onboarding_bp
    from app.routes.tenant_routes import tenant_bp
    from app.routes.user_routes import user_bp

    blueprints = [
        auth_bp,
        tenant_bp,
        user_bp,
        employee_bp,
        document_bp,
        leave_bp,
        attendance_bp,
        onboarding_bp,
        dashboard_bp,
    ]
    api_prefix = app.config['API_PREFIX'].rstrip('/')
    for blueprint in blueprints:
        blueprint_prefix = (blueprint.url_prefix or '').rstrip('/')
        app.register_blueprint(blueprint, url_prefix=f'{api_prefix}{blueprint_prefix}')
