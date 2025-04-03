# Instalační průvodce - Mezizávodová Doprava

Tento dokument popisuje instalaci a spuštění aplikace Mezizávodová Doprava pomocí Docker kontejnerů.

## Požadavky

Před instalací se ujistěte, že máte nainstalované následující komponenty:

- Docker (verze 20.10.0 nebo novější)
- Docker Compose (verze 2.0.0 nebo novější)

## Postup instalace

### 1. Stažení zdrojového kódu

- Flashka obsahuje zároveň i databázi s testovacími daty.
- Stáhněte zdrojový kód z flashky a v terminálu běžte do složky projektu.

```bash
cd Mezizavodova_doprava/production/
```

### 2. Sestavení Docker kontejnerů a spuštění aplikace

Použijte Docker Compose pro sestavení všech kontejnerů:

```bash
docker-compose up -d --build
```

Všechny kontejnery by měly být ve stavu "Up".

### 3. Přístup k aplikaci

Po úspěšném spuštění bude aplikace dostupná na:

```
http://localhost:8080/index
```

## Struktura aplikace

Aplikace se skládá z následujících komponent:

- **flask_app**: Hlavní Flask aplikace poskytující uživatelské rozhraní a business logiku
- **sqlite_db**: Kontejner spravující SQLite databázi pro ukládání dat
- **nginx**: Webový server, který zpřístupňuje aplikaci uživatelům

### Adresářová struktura aplikace

```
/
├── dev/
│   ├── docker-compose.yml
│   ├── Dockerfile.loader
│   ├── Dockerfile.watra_loader
│   ├── scripts/
│   │   ├── loader_entrypoint.sh
│   │   └── watra_loader_entrypoint.sh
│   └── config/
│       ├── sap_loader_crontab
│       └── watra_loader_crontab
├── production/
│   └── docker-compose.yml
├── application/
├── data/
│   └── SchedLine.db
├── models/
├── static/
├── templates/
├── nginx/
│   └── nginx.conf
├── app.py
└── Dockerfile
```

## Zastavení aplikace

Pro zastavení běžících kontejnerů použijte:

```bash
docker-compose down
```

### Přístup k databázi

Pro přímý přístup k SQLite databázi:

```bash
docker exec -it sqlite_db sqlite3 /data/SchedLine.db
```


