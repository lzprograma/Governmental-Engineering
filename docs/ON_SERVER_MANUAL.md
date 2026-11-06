# Manual operacional — LUNZ / On Server 0.3.0

## Inicialização

Windows: dê duplo clique em `On server.bat`.

Terminal:

```powershell
python -m pip install -e ".[server]"
python main.py On server
```

O navegador abre em `http://127.0.0.1:8765`. O terminal precisa permanecer aberto enquanto usar o painel. `CTRL+C` encerra o servidor.

## 1. Conexões API

Abra **Conexões API**. Selecione um preset ou Custom; atribua um nome à conexão; confirme a URL base e o formato da API; informe a chave no campo protegido; salve. Use **Testar** e digite um model ID válido. A descoberta de modelos pode não funcionar em provedores sem endpoint de catálogo; nesse caso, informe o identificador manualmente.

Formatos suportados: OpenAI Chat Completions, OpenAI Responses, Anthropic Messages, Gemini `generateContent` e OpenAI-compatible. “Compatível” significa que o endpoint respeita o formato escolhido, não que toda API proprietária será automaticamente interoperável.

## 2. Cadastro de cidadãos

Em **Cidadãos-modelo**, associe nome, model ID, conexão API, cargo, avatar, temperatura, limite de tokens e instrução individual. A identidade operacional de um cidadão é a combinação de registro, instrução, estado, modelo remoto e histórico; o modelo remoto pode ser compartilhado por mais de um cidadão.

## 3. Comunicação individual

Selecione um cidadão e converse. O histórico é persistido por cidadão. O serviço recupera memórias nacionais aprovadas e memórias individuais aprovadas relacionadas por busca lexical simples. As memórias são anexadas ao system prompt como dados, com a fonte registrada; a recuperação não demonstra que o conteúdo é verdadeiro.

## 4. Conselho nacional

Selecione entre 2 e 5 cidadãos ativos e configure tema, questão e 1 ou 2 rodadas. O servidor chama as APIs sequencialmente. Cada cidadão recebe os argumentos anteriores e deve analisar concordâncias, divergências e incertezas. A transcrição fica persistida. Cada turno é uma chamada real e pode consumir tokens/créditos. Falha de um provedor interrompe a deliberação e a marca como `failed`, mantendo os turnos que já foram executados.

## 5. Pesquisa web

Pesquise com DuckDuckGo HTML. Escolha **Ler e validar** para baixar texto de uma página pública. HTML e texto simples são suportados; scripts não são executados. PDF, páginas autenticadas, sites que exigem JavaScript e formulários não são suportados nesta versão. O conteúdo é truncado em limite de tamanho e apresentado para inspeção.

Use **Enviar para revisão da memória nacional** para criar uma memória candidata. A fonte e URL ficam registradas. A busca e a extração não equivalem a verificação factual: confira autor, data, domínio, contexto e qualidade antes de aprovar.

## 6. Memória nacional

É possível criar memória manual ou a partir de uma página. Todo item novo entra como `candidate`. Em **Memória nacional**, aprove ou rejeite. Somente itens aprovados são considerados na recuperação. `national` é visível a todos os cidadãos; `citizen` fica limitado ao cidadão associado. A busca atual é lexical por termos, não um banco vetorial semântico.

## 7. Aprendizagem contínua

Registre cidadão, pergunta, resposta, nota e comentário humano. Após revisão, aprove como lição individual ou nacional.

- Nota 4–5: cria exemplo positivo que pode ser exportado.
- Nota 1–3: exige correção humana (mínimo de 8 caracteres), cria memória “erro a evitar” e não vira alvo de fine-tuning.

A exportação em `/api/learning/export` gera JSONL de exemplos de conversa positivos revisados. O arquivo é matéria-prima para pipeline específico; não altera pesos por si só. APIs de inferência não fornecem um mecanismo universal de atualização de pesos.

## 8. Governo digital

O protótipo inicia seis departamentos. Crie propostas com descrição e órgão responsável; encaminhe rascunhos para revisão; aprove ou rejeite em revisão, sempre com justificativa. Eventos ficam em **Trilha de auditoria**. Isso é um workflow de demonstração, não uma deliberação legal nem uma autoridade de governo real. Não há login por cargo nem assinaturas digitais nesta versão.

## Dados e encerramento

Banco: `data/lunz_nation.sqlite3`. Chave mestra: `data/.lunz_vault.key`. Não compartilhe esses arquivos em ZIP público. Para migrar, pare o servidor e copie banco e chave em armazenamento protegido. Se perder a chave mestra, credenciais cifradas podem ficar irrecuperáveis.

Não exponha a interface em rede. O servidor é deliberadamente local.
