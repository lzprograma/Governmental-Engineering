# Arquitetura — LUNZ SOVEREIGN ACIA 0.3.0

## Domínios funcionais

```text
                GOVERNO DE LUNZ / ON SERVER
                           |
        +------------------+-------------------+
        |                  |                   |
  Registro de cidadãos  Administração       Observabilidade
        |                  |                   |
        +---- Orquestração de APIs -----------+
                    |           |
              Chat individual  Conselho multiagente
                    |           |
                    +-----+-----+
                          |
              Memória nacional / individual
                          |
                Pesquisa e aquisição web
                          |
            Aprendizagem por feedback humano
                          |
               Auditoria e fluxo de propostas
```

## Cidadão-modelo

Um cidadão é uma identidade configurável ligada a um `model_id` e a uma conexão de provedor. Possui perfil, função, avatar, instrução de sistema, parâmetros de geração, estado, histórico e memória individual. A arquitetura não duplica os pesos do modelo de cada pessoa: vários cidadãos podem chamar o mesmo modelo remoto com instruções diferentes.

## Conselho multiagente

O Conselho processa até cinco participantes e duas rodadas por deliberação. A execução é sequencial e determinística na ordem de seleção. Cada turno recebe o tema, a questão, a memória aprovada relevante e a transcrição anterior. A fala de outro cidadão é explicitamente marcada como dado não confiável. A transcrição registra modelo, cidadão, rodada e posição.

## Pesquisa web

`nation/web_research.py` contém:
- busca textual usando HTML público do DuckDuckGo;
- busca e extração de página HTTP(S);
- validação de destino por DNS/IP;
- revalidação de redirecionamentos;
- bloqueio de loopback, hosts locais, IPs privados, reservados e link-local;
- limitação do download a 2 MB por página;
- suporte a HTML/texto, sem execução de JavaScript.

A camada devolve dados e metadados de fonte. Ela não converte conteúdo de terceiros em instrução de sistema.

## Memória e aprendizagem

O `CivicStore` usa SQLite e persiste conteúdo nacional ou individual com fonte, tipo, confiança, tags, status e revisão. Somente `approved` é recuperável. O chat e o Conselho integram recuperação lexical ao contexto.

A aprendizagem operacional é baseada em feedback validado e memórias. Exemplos bem avaliados podem ser exportados como JSONL de conversas. Respostas mal avaliadas exigem correção humana e ficam marcadas como erro a evitar; não são exportadas como alvo. Alteração de pesos requer workflow próprio para cada família de modelo/checkpoint.

## Governo digital

Inclui departamentos de referência, propostas administrativas, transições de estado, justificativas e trilha de auditoria. A máquina de estados é `draft -> under_review -> approved|rejected`, com possibilidade de devolver para `draft`. O protótipo não autentica diferentes autoridades, não implementa votação/eleição e não produz validade jurídica.

## Dados

O arquivo `data/lunz_nation.sqlite3` abriga conexões, cidadãos, mensagens, departamentos, propostas, deliberações, memória, feedback e auditoria. As credenciais de API são cifradas pelo cofre Fernet do registro anterior.

## Limites para próxima maturidade

- autenticação multiusuário e RBAC;
- egress proxy corporativo, DNS pinning e isolamento de rede;
- busca web com provedor configurável, extração de PDF e crawling de domínio permitido;
- memória vetorial/híbrida e deduplicação semântica;
- filas duráveis, jobs em background, limites de custo e streaming;
- fine-tuning local/LoRA com dataset versionado, GPU, avaliação, assinatura e rollback;
- workflows de governo com múltiplos aprovadores, assinatura digital e política formal;
- replicação, backup, recuperação de desastre e auditoria externa.
