# Segurança — LUNZ SOVEREIGN ACIA 0.3.0

## Perfil de implantação

Esta distribuição é um **protótipo local, monousuário e de loopback**. Não é um ambiente de produção nem um sistema de governo apto a tratar dados oficiais classificados ou dados pessoais de cidadãos reais.

## Controles implementados

- Servidor web limitado a `127.0.0.1`, `localhost` ou `::1`.
- Middleware rejeita Host e Origin externos.
- Cabeçalhos defensivos, política CSP, `nosniff`, `DENY` para framing, `no-store`.
- Chaves API cifradas em repouso com Fernet; respostas do painel exibem apenas `has_api_key`.
- Segredos não devem ser colocados em cabeçalhos arbitrários nem parâmetros de URL.
- Pesquisa web usa GET somente, valida DNS/IP global, revalida cada redirect, limita conteúdo, não executa scripts e bloqueia localhost, loopback, IPs privados, reservados e link-local.
- Conteúdo recuperado da web e argumentos de outros cidadãos são tratados como dados não confiáveis, não instruções.
- Memórias entram como `candidate` e precisam de revisão para se tornarem recuperáveis.
- Feedback de nota baixa requer correção humana; não é exportado como resposta-alvo para fine-tuning.
- Fluxos de propostas exigem justificativa para aprovação/rejeição e registram auditoria.

## Limitações e ameaças residuais

1. O painel não tem autenticação multiusuário. Qualquer processo local com acesso ao navegador/host pode tentar interagir com o serviço. Mantenha a máquina protegida.
2. O cofre usa uma chave mestra local. Proteja `data/.lunz_vault.key`; em uma instalação séria, injete `LUNZ_VAULT_KEY` a partir de um KMS/secret manager.
3. A validação de DNS reduz SSRF, mas um sistema de produção deve usar egress proxy com política de rede, proteção contra DNS rebinding, allowlists e monitoramento de tráfego.
4. Provedores externos recebem prompts, histórico/contexto e dados enviados pelo operador. Revise contratos, região, retenção, logging e permissões de uso antes de enviar qualquer dado sensível.
5. Deliberação multiagente pode ter custo e latência. O protótipo limita 2–5 cidadãos e 1–2 rodadas, mas não substitui cotas e alertas financeiros por provedor.
6. Memória compartilhada pode propagar erros se a revisão for ruim. Mantenha fonte, escopo, confiança e status; não aprove automaticamente.
7. Auditoria SQLite é local e pode ser alterada por quem controla o host. Produção exige log append-only externo, assinatura, timestamp confiável e trilha independente.
8. O fluxo de governo digital não autentica agentes, não realiza eleições e não gera atos legais. Não use para decisões que afetem direitos, benefícios, liberdade, saúde ou segurança.

## Operação segura

- Execute apenas em máquina confiável e atualizada.
- Não exponha porta 8765 em LAN ou internet.
- Use somente dados públicos/sintéticos na avaliação inicial.
- Crie backups cifrados do banco e da chave mestra, armazenados separadamente e protegidos.
- Revogue chaves suspeitas no próprio provedor.
- Separe contas e limites de API por ambiente.
- Não habilite `allow_private_network` para endpoints que não controla.
- Avalie licença e termos de cada modelo, conjunto de dados e endpoint.

## Incidentes

Em suspeita de exposição: interrompa o processo, revogue as chaves nos provedores, preserve logs e banco para análise, gere nova chave mestra somente após planejar recriptografia/rotação, e revise a máquina. Trocar ou perder a chave mestra sem recriptografar as credenciais pode torná-las irrecuperáveis.
