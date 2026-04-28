import os
from pathlib import Path

def fix_project_encoding(root_path: str):
    """
    Varre o projeto e remove o caractere invisível BOM (U+FEFF) de arquivos de texto.
    Isso resolve o erro 'SyntaxError: invalid non-printable character U+FEFF'.
    """
    # Extensões que serão verificadas
    extensions = ('.py', '.js', '.css', '.html', '.bat', '.txt', '.md')
    # Pastas que serão ignoradas para evitar mexer em binários ou ambientes virtuais
    skip_dirs = {'.venv', '.git', '__pycache__', 'dist', 'build'}
    
    count = 0
    print(f"Iniciando limpeza de codificação em: {root_path}\n")

    for root, dirs, files in os.walk(root_path):
        # Modifica a lista dirs in-place para não entrar nas pastas ignoradas
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        
        for file in files:
            if file.endswith(extensions):
                file_path = Path(root) / file
                try:
                    # Lê o arquivo em modo binário para detectar o BOM (\xef\xbb\xbf)
                    content_bytes = file_path.read_bytes()
                    
                    if content_bytes.startswith(b'\xef\xbb\xbf'):
                        print(f"[CORRIGIDO] Removendo BOM de: {file_path.relative_to(root_path)}")
                        # utf-8-sig lê o arquivo ignorando o BOM
                        text = content_bytes.decode('utf-8-sig')
                        # Salva em UTF-8 simples (sem BOM)
                        file_path.write_text(text, encoding='utf-8')
                        count += 1
                except Exception as e:
                    print(f"[ERRO] Falha ao processar {file_path}: {e}")

    print(f"\nConcluído! {count} arquivo(s) limpo(s).")

if __name__ == "__main__":
    # Executa a limpeza a partir da pasta onde o script está localizado
    fix_project_encoding(os.path.dirname(os.path.abspath(__file__)))