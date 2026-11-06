# Matriz de implementação — 0.3.0

| Capacidade | Estado | Escopo/limite |
|---|---|---|
| Cadastro de cidadãos | Implementado | Identidades individuais associadas a APIs. |
| Conexões e adaptadores API | Implementado | 5 famílias de formato; endpoint proprietário exige adaptador adequado. |
| Chat individual | Implementado | Histórico persistente; chamadas reais dependem de credencial/model ID. |
| Conselho entre cidadãos | Implementado | 2–5 cidadãos, 1–2 rodadas, chamadas sequenciais reais. |
| Pesquisa web | Implementado | DuckDuckGo HTML + GET de páginas públicas HTML/texto; sem JS/PDF/login. |
| Memória nacional/individual | Implementado | SQLite, revisão candidate/approved/rejected, recuperação lexical. |
| Aprendizagem operacional | Implementado | Feedback humano → lição recuperável; sem alteração automática de pesos. |
| Dataset de treinamento | Implementado | JSONL com exemplos positivos revisados; não treina por si. |
| Governo digital demonstrador | Implementado | Departamentos, propostas, fluxo e auditoria local; sem validade legal/RBAC. |
| Auditoria nacional | Implementado | Eventos das áreas novas no SQLite local; não é log imutável externo. |
| Autenticação multiusuário/RBAC | Não implementado | Requisito antes de qualquer acesso remoto ou institucional. |
| Fine-tuning contínuo universal | Não implementado | Não há API universal para modificar pesos de todos provedores. |
| Operação pública/produção | Não implementado | Exige hardening, testes independentes, segurança e análise jurídica. |

## Verificação

A suíte de testes local desta distribuição deve ser executada com `python -m pytest -q`. Os testes usam chamadas simuladas para não cobrar provedores e não dependem de disponibilidade de busca externa.
