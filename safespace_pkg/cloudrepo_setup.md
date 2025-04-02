# CloudRepo Setup for SafeSpace

## For Package Publishers

### Configure .pypirc

1. Create or edit `~/.pypirc` file:
   ```
   [distutils]
   index-servers =
     cloudrepo
     pypi

   [cloudrepo]
   repository: https://griffincancode.mycloudrepo.io/repositories/safespace
   username: [repository-user-email-address]
   password: [repository-user-password]
   ```

2. Update permissions:
   ```
   chmod 600 ~/.pypirc
   ```

### Publishing to CloudRepo

1. Build distribution files:
   ```
   python -m build
   ```

2. Upload to CloudRepo:
   ```
   twine upload dist/* --repository cloudrepo
   ```

## For Package Users

### Option 1: Configure pip.conf

1. Create or edit `pip.conf`:
   - Linux/Mac: `~/.config/pip/pip.conf` or `~/.pip/pip.conf`
   - Windows: `%APPDATA%\pip\pip.ini`

2. Add CloudRepo configuration:
   ```
   [global]
   index-url = https://[username]:[password]@griffincancode.mycloudrepo.io/repositories/safespace
   trusted-host = griffincancode.mycloudrepo.io
   ```

### Option 2: Install using command line

```
pip install --index-url 'https://[username]:[password]@griffincancode.mycloudrepo.io/repositories/safespace' safespace
```

### Option 3: Configure in requirements.txt

```
--index-url https://[username]:[password]@griffincancode.mycloudrepo.io/repositories/safespace
safespace==x.y.z
```

Replace `[username]`, `[password]`, and version as appropriate. 