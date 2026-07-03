graph LR

    A[📄 Logical Circuit]
    B[🔗 Hardware Specification]

    A --> C[🟣 DAG Construction]
    B --> D[🔵 Coupling Graph]

    C --> E[🟢 Initial Layout]
    D --> E

    E -->|VF2 / SABRE Layout| F[🟠 Routing & SWAP Insertion]

    F -->|SABRE / A* / Greedy| G[🔴 Gate Optimization]

    G -->|Peephole Optimization| H[🟡 Basis Translation]

    H -->|Gate Decomposition| I[🟤 Scheduling]

    I -->|ASAP / ALAP| J[⚡ Quantum Hardware Execution]

    style C fill:#E1BEE7,stroke:#8E24AA,stroke-width:2px
    style D fill:#BBDEFB,stroke:#1E88E5,stroke-width:2px
    style E fill:#C8E6C9,stroke:#43A047,stroke-width:2px
    style F fill:#FFE0B2,stroke:#FB8C00,stroke-width:3px
    style G fill:#FFCDD2,stroke:#E53935,stroke-width:2px
    style H fill:#FFF9C4,stroke:#FDD835,stroke-width:2px
    style I fill:#D1C4E9,stroke:#5E35B1,stroke-width:2px
    style J fill:#F8BBD0,stroke:#D81B60,stroke-width:3px
```