import cloudscraper
import json
import time
import random

def translate_with_quillbot(text, source_lang='pt', target_lang='en'):
    """
    Script adaptável para traduzir com QuillBot.
    O endpoint e o payload devem ser verificados usando as Ferramentas de Desenvolvedor do navegador.
    """
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'mobile': False
        }
    )

    headers = {
        # Headers básicos são suficientes, o cloudscraper gerencia o resto.
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
        'Content-Type': 'application/json;charset=UTF-8',
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://quillbot.com/translator',
        'Origin': 'https://quillbot.com',
    }

    try:
        print("Obtendo cookies de sessão...")
        scraper.get("https://quillbot.com/translator", headers=headers)
        
        time.sleep(random.uniform(1, 2))

        # =================================================================
        # ATUALIZE AS LINHAS ABAIXO COM O QUE VOCÊ ENCONTROU NO NAVEGADOR
        # =================================================================

        # Exemplo de um possível novo endpoint (VERIFIQUE!)
        api_url = "https://quillbot.com/api/v2/translate/text" 

        # Exemplo de um possível novo payload (VERIFIQUE!)
        payload = {
            "source": source_lang,
            "target": target_lang,
            "text": text
        }
        
        # =================================================================

        print(f"Enviando texto para a API em: {api_url}")
        response = scraper.post(api_url, headers=headers, json=payload)

        if response.status_code == 200:
            response_data = response.json()
            # Adapte o caminho abaixo conforme a resposta JSON que você vê no navegador
            translated_text = response_data.get('data', [{}])[0].get('translated_text')
            
            if translated_text:
                return translated_text
            else:
                return f"Sucesso (200), mas não foi possível extrair o texto. Resposta: {response_data}"
        else:
            return f"Erro na API: {response.status_code} - Verifique o endpoint e o payload. Resposta: {response.text}"

    except Exception as e:
        return f"Ocorreu um erro inesperado: {str(e)}"

# Exemplo de uso
if __name__ == "__main__":
    texto_original = "Agora eu sei como encontrar o endpoint da API."
    resultado = translate_with_quillbot(texto_original)
    
    print("-" * 30)
    print(f"Texto original: {texto_original}")
    print(f"Texto traduzido: {resultado}")
    print("-" * 30)