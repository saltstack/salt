# Remote CLI Authentication Design

## Date
2026-10-24

## Overview
Design for implementing AES-based authentication for remote Salt CLI clients, mirroring the existing minion authentication flow while supporting future extensibility to JWT/OAuth.

## Architecture Decisions
1. **Authentication Method**: AES encryption (same as minions) with architecture allowing future JWT/OAuth support
2. **Permission Model**: External authentication (eauth) system for authorization
3. **Key Management**: Manual acceptance workflow (like minion keys)

## Authentication Flow

### Client Side (AsyncAuth)

**Key Files:**
- `client.pem` - Client's private RSA key
- `client.pub` - Client's public RSA key
- `client_master.pub` - Master's public RSA key (received during auth)

**Flow:**
1. **Key Generation** (first run):
   - Check if `client.pem` exists in PKI directory
   - If not, generate RSA keypair (4096-bit default)
   - Store private key: `$pki_dir/client.pem`
   - Store public key: `$pki_dir/client.pub`

2. **Authentication Request**:
   ```python
   payload = {
       "cmd": "_auth",
       "id": "<client-id>",           # From config or hostname
       "pub": "<client-public-key>",  # Contents of client.pub
       "nonce": "<uuid>",             # For replay protection
       "enc_algo": "OAEP-SHA1",       # From config
       "sig_algo": "PKCS1v15-SHA1",   # From config
       "token": "<encrypted-token>"   # If we have master's pubkey
   }
   ```

3. **Send to Master**:
   - Use `AsyncReqChannel.factory(opts, crypt="clear")`
   - Send payload to master via clear channel
   - Master processes via `salt/channel/server.py._auth()`

4. **Handle Response**:
   ```python
   response = {
       "enc": "pub",
       "pub_key": "<master-public-key>",
       "publish_port": 4506,
       "aes": "<encrypted-aes-key>",      # Encrypted with client's pubkey
       "session": "<encrypted-session-key>", # Encrypted with client's pubkey
       "sig": "<aes-key-signature>",
       "nonce": "<same-nonce-from-request>"
   }
   ```

5. **Decrypt Credentials**:
   - Verify nonce matches request
   - Verify master's signature
   - Decrypt AES key using client's private key
   - Decrypt session key using client's private key
   - Store in `AsyncAuth.creds_map` for reuse

6. **Create Crypticle**:
   - Create `Crypticle(opts, aes_key)` for message encryption
   - Create `Crypticle(opts, session_key)` for session encryption
   - Future communications use AES encryption

### Master Side (salt/channel/server.py)

**Key Storage:**
- Uses cache-based storage: `self.cache.fetch("client_keys", client_id)`
- Key states: "pending", "accepted", "rejected"
- Denied keys stored separately: `self.cache.fetch("client_denied_keys", client_id)`

**Flow:**
1. **Receive Auth Request**:
   - Extract: id, pub, nonce, enc_algo, sig_algo
   - Validate client_id format

2. **Key State Check**:
   ```python
   key = self.cache.fetch("client_keys", load["id"])
   # Returns: {"pub": "<pubkey>", "state": "pending|accepted|rejected"}
   ```

3. **State Handling**:
   - **No key (new client)**:
     - Check auto-reject file
     - Check auto-sign file
     - Default: Store as pending
     - Return `{"ret": True}` (pending) or `{"ret": False}` (rejected)

   - **Pending key**:
     - Compare public keys
     - If match: Return `{"ret": True}` (still pending)
     - If mismatch: Deny and store in client_denied_keys

   - **Accepted key**:
     - Compare public keys
     - If match: Proceed to generate AES response
     - If mismatch: Deny (possible compromise attempt)

   - **Rejected key**:
     - Return `{"ret": False}`

4. **Generate Auth Response** (if accepted):
   ```python
   # Load client's public key
   pub = salt.crypt.PublicKey.from_str(key["pub"])

   # Encrypt AES key with client's public key
   ret = {
       "enc": "pub",
       "pub_key": self.master_key.get_pub_str(),
       "publish_port": self.opts["publish_port"],
       "aes": pub.encrypt(aes_key, enc_algo),
       "session": pub.encrypt(session_key, enc_algo),
       "sig": self.master_key.encrypt(aes_digest),
   }
   ```

5. **Fire Auth Event**:
   ```python
   self.event.fire_event({
       "result": True,
       "act": "accept|pend|reject|deny",
       "id": load["id"],
       "pub": load["pub"]
   }, tagify(prefix="auth"))
   ```

## Code Changes Required

### 1. salt/crypt.py - AsyncAuth Class

**Changes:**
```python
def __singleton_init__(self, opts, io_loop=None):
    # Determine role-specific paths
    if self.opts.get("__role") == "client":
        self.pub_path = os.path.join(self.opts["pki_dir"], "client.pub")
        self.rsa_path = os.path.join(self.opts["pki_dir"], "client.pem")
        self.mpub = "client_master.pub"  # Master's public key
    elif self.opts["__role"] == "syndic":
        self.pub_path = os.path.join(self.opts["pki_dir"], "minion.pub")
        self.rsa_path = os.path.join(self.opts["pki_dir"], "minion.pem")
        self.mpub = "syndic_master.pub"
    else:  # minion
        self.pub_path = os.path.join(self.opts["pki_dir"], "minion.pub")
        self.rsa_path = os.path.join(self.opts["pki_dir"], "minion.pem")
        self.mpub = "minion_master.pub"
```

**Key generation:**
```python
def get_keys(self):
    if self._private_key is None:
        salt.utils.verify.check_path_traversal(self.opts["pki_dir"], user)

        if not os.path.exists(self.rsa_path):
            log.info("Generating keys: %s", self.opts["pki_dir"])
            (priv, pub) = gen_keys(self.opts["keysize"])

            # Determine cache key based on role
            if self.opts.get("__role") == "client":
                cache_key_priv = "client.pem"
                cache_key_pub = "client.pub"
            else:
                cache_key_priv = "minion.pem"
                cache_key_pub = "minion.pub"

            self.cache.store("master_keys", cache_key_priv, priv)
            self.cache.store("master_keys", cache_key_pub, pub)
        else:
            # Load existing key
            if self.opts.get("__role") == "client":
                priv = self.cache.fetch("master_keys", "client.pem")
            else:
                priv = self.cache.fetch("master_keys", "minion.pem")

        self._private_key = PrivateKey.from_str(priv, None)
    return self._private_key
```

### 2. salt/channel/server.py - ReqServerChannel._auth()

**Changes to support client keys:**
```python
def _auth(self, load, sign_messages=False, version=0):
    # ... existing validation ...

    # Determine if this is a client or minion based on opts or load
    # For now, we'll use the same flow but with different cache keys
    is_client = load.get("role") == "client"  # Could also check other indicators

    if is_client:
        cache_key = "client_keys"
        denied_key = "client_denied_keys"
    else:
        cache_key = "keys"
        denied_key = "denied_keys"

    # Fetch key from appropriate cache
    key = self.cache.fetch(cache_key, load["id"])
    denied = self.cache.fetch(denied_key, load["id"]) or []

    # ... rest of authentication logic uses cache_key and denied_key ...

    # Store in appropriate cache
    self.cache.store(cache_key, load["id"], key)
```

**Note:** We may need a better way to distinguish clients from minions. Options:
- Add "role" field to auth payload
- Use different port/endpoint for client auth
- Infer from id naming convention (e.g., "client-*")

### 3. salt/client/__init__.py - RemoteClient

**Implement authentication:**
```python
class RemoteClient(LocalClient):
    """
    Remote client that authenticates with the master using AES encryption.
    Similar to minion authentication but for CLI clients.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.opts["__role"] = "client"  # Set role for AsyncAuth
        self.auth = None

    async def authenticate(self):
        """
        Authenticate with the master using AES encryption.
        Must be called before executing commands.
        """
        if self.auth is None:
            self.auth = salt.crypt.AsyncAuth(self.opts, self.io_loop)

        # This will generate keys if needed and authenticate
        await self.auth.authenticate()

    def cmd(self, *args, **kwargs):
        """
        Execute a command on minions after authenticating.
        """
        # Ensure we're authenticated
        if not self.auth or not self.auth.authenticated:
            # Need to run async authentication
            raise SaltClientError(
                "Client not authenticated. Call authenticate() first."
            )

        # Use authenticated channel for communication
        return super().cmd(*args, **kwargs)
```

### 4. salt/config/__init__.py

**Already has:**
- `encryption_algorithm: "OAEP-SHA1"`
- `signing_algorithm: "PKCS1v15-SHA1"`

**May need to add:**
- `client_pki_dir`: Path for client keys (default: `$pki_dir/clients` on master)
- `client_id`: Client identifier (default: hostname or from config)

### 5. salt/key.py - ClientKey Class

**Already has skeleton, needs implementation:**
```python
class ClientKey(Key):
    """
    Manage client keys on the master.
    Similar to minion key management.
    """
    KIND = "client"
    ACC = "clients"           # Accepted keys
    PEND = "clients_pre"      # Pending keys
    REJ = "clients_rejected"  # Rejected keys
    DEN = "clients_denied"    # Denied keys

    def list_keys(self):
        """List all client keys by state."""
        return super().list_keys()

    def accept(self, match, include_rejected=False, include_denied=False):
        """Accept client key(s)."""
        return super().accept(match, include_rejected, include_denied)

    def reject(self, match, include_accepted=False, include_denied=False):
        """Reject client key(s)."""
        return super().reject(match, include_accepted, include_denied)

    def delete_key(self, match):
        """Delete client key(s)."""
        return super().delete_key(match)
```

## Permission Model (eauth)

After initial AES authentication, clients will use eauth for command authorization. This is already implemented in Salt for API access.

**Flow:**
1. Client authenticates with master (gets AES key)
2. Client includes eauth credentials in command payload:
   ```python
   {
       "eauth": "pam",       # Auth backend
       "username": "alice",   # Username
       "password": "secret",  # Password or token
       "tgt": "*",           # Target
       "fun": "test.ping"    # Function
   }
   ```
3. Master checks permissions via `LoadAuth.check_authentication()`
4. Master authorizes via `CkMinions.auth_check()`
5. If authorized, execute command

**Config example:**
```yaml
# /etc/salt/master.d/client_eauth.conf
external_auth:
  pam:
    alice:
      - 'web*':
        - test.*
        - pkg.*
    bob:
      - '*':
        - test.ping
```

## Security Considerations

1. **Key Storage**:
   - Client private keys stored in `~/.salt/pki/` or `/etc/salt/pki/`
   - Permissions: 0400 (read-only by owner)
   - Never transmitted over network

2. **Authentication**:
   - Public key sent in clear (public information)
   - AES key encrypted with client's public key
   - Only client with private key can decrypt

3. **Authorization**:
   - eauth provides fine-grained access control
   - Separate from authentication
   - Supports multiple backends (PAM, LDAP, etc.)

4. **Key Management**:
   - Manual acceptance by default (like minions)
   - Auto-signing supported but discouraged
   - Rejected keys cannot re-authenticate

## Future Extensibility

The design allows for future JWT/OAuth support:

1. **Plugin Architecture**:
   - Create `salt/auth/client/` directory
   - Implement `AESAuth`, `JWTAuth`, `OAuthAuth` classes
   - Factory pattern to select auth method

2. **Config-driven**:
   ```yaml
   client_auth_method: aes  # or jwt, oauth
   ```

3. **Interface**:
   ```python
   class ClientAuth:
       def authenticate(self, opts):
           """Return auth credentials"""
           pass

       def get_headers(self):
           """Return auth headers for requests"""
           pass
   ```

## Testing Strategy

1. **Unit Tests**:
   - AsyncAuth with `__role="client"`
   - ClientKey CRUD operations
   - Cache storage/retrieval for client_keys

2. **Integration Tests**:
   - Full auth flow: key generation → auth request → AES response
   - Key acceptance workflow
   - eauth permission checks

3. **Functional Tests**:
   - End-to-end: `salt '*' test.ping` from remote client
   - Multiple clients connecting simultaneously
   - Key rejection and denial scenarios

## Migration Path

1. **Phase 1** (Current): Implement AES authentication
   - Modify AsyncAuth for client support
   - Update channel server for client keys
   - Implement RemoteClient authentication

2. **Phase 2**: eauth Integration
   - Add eauth to RemoteClient commands
   - Test with PAM/LDAP backends
   - Document permission configuration

3. **Phase 3**: Key Management
   - Implement salt-key support for clients
   - Add client key listing/acceptance/rejection
   - Create admin tools

4. **Phase 4**: Future Auth Methods
   - Design plugin architecture
   - Implement JWT auth (optional)
   - Implement OAuth auth (optional)

## Open Questions

1. **Client Identification**:
   - How to distinguish client auth requests from minion auth requests?
   - Options:
     a) Add "role" field to payload ✓
     b) Use different endpoint/port
     c) Naming convention (client-* vs minion names)

2. **Backward Compatibility**:
   - Should RemoteClient fall back to LocalClient if no auth configured?
   - How to handle existing salt CLI installations?

3. **Multi-Master**:
   - How does client key work with multiple masters?
   - Should clients have different keys per master?

## References

- Existing minion auth: `salt/crypt.py::AsyncAuth`
- Master auth handler: `salt/channel/server.py::ReqServerChannel._auth()`
- eauth system: `salt/auth/__init__.py::LoadAuth`
- Key management: `salt/key.py::Key`
