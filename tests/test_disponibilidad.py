from fastapi.testclient import TestClient
from main import app 

client = TestClient(app)

def test_listar_solo_unidades_disponibles():
    """Prueba T13: Verifica que solo se muestren unidades Disponibles y oculte las Usadas/Vencidas."""
    response = client.get("/stock")
    assert response.status_code == 200
    html = response.text
    
    assert "U-100" in html
    assert "U-101" in html
    assert "U-102" not in html

def test_filtrar_por_tipo_componente():
    """Prueba T14: Verifica que el filtro de componente funcione."""
    response = client.get("/stock?tipo=Plaquetas")
    assert response.status_code == 200
    html = response.text
    
    assert "U-101" in html 
    assert "U-100" not in html 

def test_mostrar_aviso_sin_resultados():
    """Prueba T15: Verifica que aparezca el aviso cuando los filtros no coinciden con nada."""
    response = client.get("/stock?tipo=Plaquetas&grupo=O%2B")
    assert response.status_code == 200
    html = response.text
    
    assert "No se encontraron unidades disponibles con esos filtros." in html
    assert "U-100" not in html
    assert "U-101" not in html