# Declaração de Uso de IA Generativa

| Campo | Detalhe |
|---|---|
| Ferramenta e modelo utilizados | Claude (Anthropic) |
| Finalidade | Apoio no diagnóstico de um problema de rede entre containers, na interpretação de saídas de comandos de diagnóstico de processos e chamadas de sistema, na identificação do tipo de licença de um repositório de terceiros, e na estruturação/organização deste relatório a partir dos dados coletados pelo próprio discente. |
| Prompts relevantes (até 5) | 1) Diagnóstico do erro de conexão entre Open WebUI e Ollama (rede Docker); 2) Interpretação das chamadas de sistema (futex, mmap, accept4/read) do strace-resumo.txt; 3) Interpretação da hierarquia de processos do pstree -p, com distinção entre processo e thread; 4) Identificação do tipo de licença do repositório do Open WebUI; 5) Interpretação dos tempos medidos nos 12 experimentos da Parte C. |
| Sugestões aproveitadas | Estrutura do relatório, roteiro de comandos para as Partes B e C, script de automação dos 12 experimentos, interpretação de logs e saídas de comandos. |
| Sugestões corrigidas/rejeitadas | Uma resposta gerada pelo próprio modelo Phi-4-mini durante um teste na interface (não pela IA de apoio) definiu incorretamente o termo "processo de ruído"; esse erro foi identificado e não foi incorporado ao relatório. |
| Erros encontrados | Nenhum erro relevante nas explicações fornecidas pela IA de apoio foi identificado após verificação cruzada com as saídas reais dos comandos. |
| Verificação | Todos os comandos foram executados e validados diretamente no terminal pelo próprio discente; as saídas (ps, pstree, htop, top -H, strace, resultados.csv) foram conferidas manualmente antes de serem documentadas. |