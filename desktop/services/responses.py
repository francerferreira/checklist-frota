from flask import jsonify

def api_response(success: bool, data: any = None, error: str = None, status_code: int = 200):
    """
    Implementa a resposta padronizada da API para todo o sistema.
    Garante que o Web App e o Desktop recebam sempre a mesma estrutura:
    { "success": boolean, "data": mixed, "error": string }
    """
    payload = {"success": success}
    if success:
        payload["data"] = data
    else:
        payload["error"] = error
    return jsonify(payload), status_code