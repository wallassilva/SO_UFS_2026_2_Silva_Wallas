# Ficha da Camada de Aplicação — Open WebUI

| Campo | Valor |
|---|---|
| Nome | Open WebUI |
| URL do repositório | https://github.com/open-webui/open-webui |
| Autor/organização | Open WebUI Inc. (criado por Timothy Jaeryang Baek) |
| Imagem utilizada | ghcr.io/open-webui/open-webui:main |
| Digest (versão exata) | sha256:1a6399d237dc392a2313e0ca826020b3fd5d22536357840eb63393d18dc8b924 |
| Data de acesso | 15/09/2026 |
| Licença | Open WebUI License — licença própria, com estrutura semelhante a BSD-3-Clause, acrescida de cláusula que restringe a remoção do branding "Open WebUI" em implantações com mais de 50 usuários simultâneos ou uso comercial sem licença específica. Não é mais MIT desde uma versão anterior do projeto. |
| Finalidade | Interface web de chat para modelos servidos pelo Ollama, comunicando-se via API HTTP local (porta 11434) |
| Dependências | Docker; Ollama rodando localmente e acessível pela rede do container |
| Comando de instalação/execução | Ver README.md ou Seção 6.4 do relatório |
| Adaptações realizadas | Configuração de OLLAMA_HOST=0.0.0.0:11434 para permitir conexão do container ao serviço do Ollama no host |
| Limitações/erros encontrados | Erro inicial de conexão "Cannot connect to host.docker.internal:11434", resolvido ajustando o host de escuta do Ollama |