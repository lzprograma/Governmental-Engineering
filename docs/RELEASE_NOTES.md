# Release notes — 0.3.0

## Novidades

- Estruturado o Conselho nacional para conversas multiagente persistidas entre cidadãos.
- Adicionado mecanismo de pesquisa DuckDuckGo HTML e leitura de páginas web públicas.
- Criada memória nacional e individual com proveniência, confiança e revisão humana.
- Integrada a recuperação de memórias aprovadas em chat individual e deliberações.
- Adicionado ciclo de feedback humano e lições de aprendizagem persistente.
- Exemplos positivos revisados podem ser exportados em JSONL.
- Feedback negativo exige correção humana e é guardado como “erro a evitar”, sem ser exportado como resposta-alvo.
- Criados departamentos, propostas administrativas, fluxo de revisão/aprovação/rejeição e auditoria.
- Interface On Server recebeu novas áreas para Conselho, Web, Memória, Aprendizagem e Governo digital.
- Busca web bloqueia hosts/IPs privados, revalida redirects e limita tamanho transferido.

## Testes

- 30 testes aprovados no ambiente de desenvolvimento desta release.
- Provedores externos não são chamados pela suíte de testes; integração real requer credenciais e pode gerar cobrança.

## Limites conhecidos

- Aprendizagem significa memória/recuperação com revisão humana, não atualização universal de pesos.
- Governo digital é workflow demonstrador local, não sistema juridicamente válido.
- Pesquisa web cobre páginas públicas HTML/texto, sem JavaScript, login ou PDF.
- Painel monousuário, loopback e sem autenticação multiusuário.
