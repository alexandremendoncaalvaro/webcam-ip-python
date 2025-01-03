# Webcam IP Server v2.0.14

Uma aplicação desktop para transmitir webcam, vídeos ou imagens através de HTTP ou WebSocket.

## 🌟 Funcionalidades

- 📹 Suporte para múltiplas fontes de vídeo:
  - Webcams conectadas
  - Arquivos de vídeo (MP4, AVI, MKV)
  - Imagens estáticas (JPG, PNG)
- 🔄 Protocolos de transmissão:
  - HTTP (compatível com navegadores)
  - WebSocket (baixa latência)
- 🎛️ Configurações ajustáveis:
  - Resolução de vídeo (até 1920x1080)
  - Porta de transmissão
  - Seleção de câmera
- 👀 Visualização em tempo real
- 💾 Salva configurações automaticamente
- 🔗 URLs clicáveis para fácil acesso
- 🖼️ Ícone personalizado

## 📋 Requisitos

- Python 3.8 ou superior
- Windows 10/11
- Webcam ou arquivos de mídia para transmitir

## 🚀 Instalação

1. Clone o repositório:

```bash
git clone https://github.com/seu-usuario/webcam-ip-python.git
cd webcam-ip-python
```

2. Crie um ambiente virtual:

```bash
python -m venv .venv
.venv\Scripts\activate
```

3. Instale as dependências:

```bash
pip install -r requirements.txt
```

## 💻 Uso

1. Execute o programa:

```bash
python webcam_ip.py
```

2. Na interface:

   - Selecione o tipo de fonte (Webcam, Vídeo ou Imagem)
   - Escolha a resolução desejada
   - Selecione o protocolo (HTTP ou WebSocket)
   - Configure a porta (padrão: 5000)
   - Clique em "Start Preview" para visualizar
   - Clique em "Start Server" para iniciar a transmissão

3. Acesse o stream:
   - HTTP: Clique no link ou acesse `http://seu-ip:porta`
   - WebSocket: Clique no link para abrir o cliente de exemplo

## 🔧 Configurações

- As configurações são salvas automaticamente em `settings.json`
- Configurações salvas:
  - Tipo de fonte
  - Câmera selecionada
  - Resolução
  - Protocolo
  - Porta
  - Último arquivo de vídeo/imagem usado

## 🌐 Protocolos

### HTTP

- Compatível com qualquer navegador
- Maior compatibilidade
- Latência média

### WebSocket

- Menor latência
- Requer cliente WebSocket
- Cliente de exemplo incluído

## 📝 Notas

- Para câmeras USB, conecte antes de iniciar o programa
- A porta selecionada deve estar disponível
- Firewall pode precisar de liberação para acesso externo
- Em caso de erro, verifique se a porta não está em uso

## 🐛 Problemas Conhecidos

- Algumas webcams podem não ser detectadas corretamente
- Pode haver atraso em redes congestionadas
- Resolução máxima limitada pelo hardware

## 🔄 Atualizações na v2.0.14

- Corrigido problema com serviço WebSocket
- Melhorado gerenciamento de recursos
- Interface mais responsiva
- Salvamento automático de configurações
- URLs clicáveis para fácil acesso
- Suporte a múltiplas câmeras
- Melhor tratamento de erros

## 🤝 Contribuindo

1. Faça um Fork
2. Crie uma branch (`git checkout -b feature/sua-feature`)
3. Commit suas mudanças (`git commit -m 'Adiciona feature'`)
4. Push para a branch (`git push origin feature/sua-feature`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.
