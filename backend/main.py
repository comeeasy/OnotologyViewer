from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import classes, config, data_properties, datasets, graphs, individuals, namespaces, object_properties, sparql_editor, reasoning, shacl, rules, datasources, universal_ns

app = FastAPI(
    title="OntologyViewer API",
    version="0.1.0",
    description="Apache Jena Fuseki 기반 온톨로지 관리 API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(config.router)
app.include_router(datasets.router)
app.include_router(graphs.router)
app.include_router(namespaces.router)
app.include_router(classes.router)
app.include_router(object_properties.router)
app.include_router(data_properties.router)
app.include_router(individuals.router)
app.include_router(sparql_editor.router)
app.include_router(reasoning.router)
app.include_router(shacl.router)
app.include_router(rules.router)
app.include_router(datasources.router)
app.include_router(universal_ns.router)
