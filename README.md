# Instalační průvodce - Mezizávodová Doprava

Tento dokument popisuje instalaci a spuštění aplikace Mezizávodová Doprava pomocí Docker kontejnerů.

## Požadavky

Před instalací se ujistěte, že máte nainstalované následující komponenty:

- Docker (verze 20.10.0 nebo novější)
- Docker Compose (verze 2.0.0 nebo novější)

## Postup instalace z flash disku

### 1. Stažení zdrojového kódu

- Flashka obsahuje zároveň i databázi s testovacími daty.
- ve Flash disku:

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

## Postup instalace z git (bez databáze)

### 1. Stažení zdrojových souborů z github

```bash
git clone -b public-branch https://github.com/Makovsky08/Interplant-transport.git Mezizavodova_doprava
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
├── production/
│   └── docker-compose.yml
├── application/
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

### Přístup k aplikaci

Pro přístup k exisující instanci aplikace na veřejné ip adrese:

- [http://51.21.180.93/index](http://51.21.180.93/index)


