# crm-clienti-contratti

## Risoluzione dei problemi

### `SyntaxError: invalid decimal literal` alla riga con `index ...`

Se, avviando `app.py`, Python mostra un errore simile a:

```
File "app.py", line 2
  index 3495ac3ab538ddc5d26e4f36eb6d72e5e20f9765..411c7a88e6180c6abf7efb3193f3e7b0b7391861 100644
        ^
SyntaxError: invalid decimal literal
```

significa che nel file è stato incollato per sbaglio un diff Git (ad esempio dopo aver eseguito un comando `git apply` con sintassi errata). Rimuovi tutte le righe che iniziano con `index`, `@@`, `+` o `-` all'inizio del file, poi salva `app.py` e rilancialo.

Se preferisci un aiuto automatico, esegui:

```
python scripts/repair_app_from_diff.py
```

Il comando ricostruisce `app.py` prendendo solo le righe corrette dal diff incollato (supporta anche la modalità anteprima con `--dry-run`). In alternativa, puoi sempre ripristinare il file dall'ultimo commit funzionante con `git checkout -- app.py`.
