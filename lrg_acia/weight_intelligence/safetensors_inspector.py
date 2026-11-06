"""WIE de leitura segura: inspeciona apenas o cabeçalho do formato Safetensors.

Não desserializa pesos, não executa código do checkpoint e não atribui semântica a tensores.
"""
from __future__ import annotations
import hashlib
import json
import struct
from pathlib import Path
from typing import Any
from ..core.contracts import ModelArtifact


class WeightInspectionError(RuntimeError):
    pass


class WeightIntelligenceEngine:
    MAX_HEADER_BYTES = 16 * 1024 * 1024

    def inspect_safetensors(self, artifact: ModelArtifact) -> dict[str, Any]:
        if not artifact.authorized_for_weight_analysis:
            raise WeightInspectionError("O artefato não possui autorização registrada para análise de pesos.")
        if artifact.access_mode != "local_weights" or not artifact.local_path:
            raise WeightInspectionError("WIE exige caminho local e acesso por pesos autorizados; API não é inspecionável.")
        path = Path(artifact.local_path).expanduser().resolve()
        if path.suffix != ".safetensors" or not path.is_file():
            raise WeightInspectionError("Somente arquivos .safetensors existentes são aceitos nesta rotina.")
        size = path.stat().st_size
        if size < 10:
            raise WeightInspectionError("Arquivo muito pequeno para ser um Safetensors válido.")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
            stream.seek(0)
            header_len = struct.unpack("<Q", stream.read(8))[0]
            if header_len <= 1 or header_len > self.MAX_HEADER_BYTES or header_len + 8 > size:
                raise WeightInspectionError("Comprimento do cabeçalho inválido ou fora do limite.")
            header_bytes = stream.read(header_len)
        actual_hash = digest.hexdigest()
        if artifact.artifact_hash and artifact.artifact_hash.lower() != actual_hash.lower():
            raise WeightInspectionError("SHA-256 do arquivo não corresponde ao manifesto do artefato.")
        try:
            header = json.loads(header_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WeightInspectionError("Cabeçalho Safetensors inválido.") from exc
        data_bytes = size - (8 + header_len)
        tensors = []
        for name, metadata in header.items():
            if name == "__metadata__":
                continue
            if not isinstance(metadata, dict):
                raise WeightInspectionError(f"Metadado inválido para tensor {name!r}.")
            shape = metadata.get("shape")
            offsets = metadata.get("data_offsets")
            dtype = metadata.get("dtype")
            if not isinstance(shape, list) or not isinstance(offsets, list) or len(offsets) != 2:
                raise WeightInspectionError(f"Shape/offset inválido para tensor {name!r}.")
            start, end = offsets
            if not all(isinstance(x, int) for x in offsets) or start < 0 or end < start or end > data_bytes:
                raise WeightInspectionError(f"Offsets fora da região de dados para tensor {name!r}.")
            if not all(isinstance(x, int) and x >= 0 for x in shape):
                raise WeightInspectionError(f"Shape inválido para tensor {name!r}.")
            tensors.append({"name": name, "dtype": dtype, "shape": shape,
                            "data_bytes": end - start, "offsets": offsets})
        return {
            "model_id": artifact.model_id,
            "provider": artifact.provider,
            "snapshot": artifact.snapshot,
            "license": artifact.license_name,
            "file": path.name,
            "file_size_bytes": size,
            "sha256": actual_hash,
            "tensor_count": len(tensors),
            "tensors": tensors,
            "metadata": header.get("__metadata__", {}),
            "analysis_scope": "header_only_no_weight_values_loaded",
            "interpretation_limit": "Tensor metadata does not establish semantic meaning or capability.",
        }

    @staticmethod
    def to_markdown(report: dict[str, Any]) -> str:
        lines = [
            f"# WIE — Relatório de inventário: {report['model_id']}", "",
            f"- Fornecedor: {report['provider']}",
            f"- Snapshot: {report.get('snapshot') or 'não informado'}",
            f"- Licença declarada: {report['license']}",
            f"- Arquivo: `{report['file']}` ({report['file_size_bytes']} bytes)",
            f"- SHA-256: `{report['sha256']}`",
            f"- Tensores: {report['tensor_count']}",
            f"- Escopo: `{report['analysis_scope']}`", "",
            "## Inventário de tensores", "",
            "| Tensor | Tipo | Shape | Bytes |", "|---|---|---:|---:|",
        ]
        for tensor in report["tensors"]:
            lines.append(f"| `{tensor['name']}` | {tensor['dtype']} | `{tensor['shape']}` | {tensor['data_bytes']} |")
        lines += ["", "## Limitações", "", report["interpretation_limit"],
                  "Este relatório não carrega valores dos pesos, não executa arquivos e não infere o que o modelo 'pensa'.", ""]
        return "\n".join(lines)
