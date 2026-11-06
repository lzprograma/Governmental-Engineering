"""Seleção explícita de método de raciocínio por família de tarefa."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ReasoningPlan:
    method: str
    rationale: str
    requires_external_verification: bool


class ReasoningEngine:
    KEYWORDS = {
        "formal": ("prova", "teorema", "demonstre", "sat", "smt", "lógica"),
        "calculation": ("calcule", "quanto", "equação", "integral", "derivada"),
        "simulation": ("simule", "cenário", "dinâmica", "transição"),
        "search": ("otimize", "rota", "escalone", "planeje"),
        "causal": ("causa", "efeito causal", "intervenção", "contrafactual"),
    }

    def select(self, prompt: str, domain: str = "general") -> ReasoningPlan:
        lower = prompt.casefold()
        for method, terms in self.KEYWORDS.items():
            if any(term in lower for term in terms):
                return ReasoningPlan(method, f"Termos da tarefa indicam método {method}.", method in {"formal", "calculation", "causal"})
        if domain in {"science", "engineering", "mathematics"}:
            return ReasoningPlan("abduction_then_verification", "Hipóteses devem ser confrontadas com evidência e verificadores.", True)
        return ReasoningPlan("structured_analysis", "Decompor a tarefa e explicitar evidências, limites e incerteza.", False)
