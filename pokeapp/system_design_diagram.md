# Pokédex lore validation — system design

This diagram matches the pipeline in `ai_validator_pokemon.py`: PokeAPI data is assembled into a **retrieval bundle**, each **prompt arm** generates lore via Ollama **`/api/generate`**, then an **AI reviewer** calls Ollama **`/api/chat`** with JSON mode using the **full bundle** as ground truth. Results are saved as report text files, a scores CSV, and printed statistics.

```mermaid
flowchart TB
  pokeapi["PokeAPI\nspecies + generation + /pokemon"]
  bundle["Retrieval bundle\nJSON ground truth\nspecies_lore · generation · pokemon_snapshot"]

  pokeapi --> bundle

  subgraph arms["Experiment: prompt arms"]
    ai["AI_POKEMON\nai_pokemon.py\nspecies JSON only"]
    rag["RAG\nfull bundle in prompt"]
    partial["RAG_PARTIAL\npartial JSON"]
    norag["NON_RAG\nname only, no JSON"]
  end

  bundle --> arms
  ai --> gen["Ollama /api/generate\nlore writer"]
  rag --> gen
  partial --> gen
  norag --> gen

  gen --> reports["Generated lore\n.txt per arm × species"]

  reports --> review["AI reviewer\nOllama /api/chat + JSON\nhallucination counts\nprecision · groundedness"]
  bundle -->|"always full bundle\nfor audit"| review

  review --> out["Outputs\nvalidation_experiment_scores.csv\nplots · ANOVA / Welch t"]

  style pokeapi fill:#d5f5e3
  style bundle fill:#fdebd0
  style arms fill:#f5eef8
  style gen fill:#d6eaf8
  style reports fill:#f9e79f
  style review fill:#fadbd8
  style out fill:#eaeded
```

To regenerate this file and the optional PNG, run:

- `python3 diagram_validation_system.py` — updates this Markdown
- `python3 diagram_validation_system.py --png` — also writes `validation_runs/run_default/system_design_diagram.png`
