"""
seed_data.py - clean, curated seed data for the Q&A platform.

Replaces generate_data.py + migrate_votes.py + index_all.py in one run:
  * MongoDB : users, questions, answers  (integer _ids everywhere)
  * Redis   : answer:{id}:votes + "leaderboard" (username -> total votes)
  * Chroma  : qa_questions collection (cosine), one doc per question title

Seeded users all have the password:  test1234
Run:  python seed_data.py            (append)
      python seed_data.py --reset    (wipe and rebuild)
Default: ADD ONLY and safe to rerun: questions already in Mongo (by title) are skipped, seeded
users are reused, so running it again after adding more questions only inserts the new ones.
 New ids continue after your highest existing integer ids, existing
data is untouched, Redis votes/leaderboard are added, Chroma is upserted.
Run it with --reset to wipe everything first (drops the 3 Mongo collections, deletes
answer:* and leaderboard in Redis, recreates the Chroma collection).
"""
import random
from datetime import datetime, timedelta, timezone

random.seed(7)

PASSWORD = "test1234"
QUESTIONS = [
    # ---------------- cybersecurity ----------------
    ("cybersecurity",
     "Storing user passwords safely with Argon2id instead of SHA-256",
     "My auth service hashes passwords with `hashlib.sha256(password.encode()).hexdigest()` and stores them in the database.",
     "Fast hashes like SHA-256 can be brute-forced at billions of guesses per second on modern GPUs. Use a memory-hard password hashing algorithm like **Argon2id** (via `argon2-cffi` or `pwdlib`), which automatically generates a unique per-user salt and resists GPU/ASIC cracking.",
     "Verify passwords with constant-time verification built into the library and rehash transparently on login whenever you increase memory/time cost parameters."),
    ("cybersecurity",
     "Preventing Server-Side Request Forgery (SSRF) when fetching user-supplied URLs",
     "My app lets users paste an image URL to import an avatar, and a pentester used it to hit `http://169.254.169.254/latest/meta-data/`.",
     "Resolve the hostname to its IP address *before* connecting, block all private/loopback/link-local CIDR ranges (`127.0.0.0/8`, `10.0.0.0/8`, `169.254.0.0/16`, `::1`, `fc00::/7`), disable automatic HTTP redirects (or re-validate every redirect target), and restrict schemes to `https://`.",
     "On AWS, enforce IMDSv2 (`HttpTokens: required`) so simple GET-based SSRF can never read EC2 instance credentials."),
    ("cybersecurity",
     "Why storing JWTs in `localStorage` is risky compared to `HttpOnly` cookies",
     "I store my access and refresh JWTs in `localStorage` so my SPA can attach them as `Authorization: Bearer` headers.",
     "Any XSS vulnerability or compromised third-party script on your page can read `localStorage` and exfiltrate tokens silently. Store session/refresh tokens in `HttpOnly; Secure; SameSite=Lax` (or `Strict`) cookies so JavaScript can never access them.",
     "If you use cookie-based auth, pair it with CSRF protection (e.g., double-submit token or `Origin`/`Referer` header verification on state-changing requests)."),
    ("cybersecurity",
     "Defending against SQL Injection even when building dynamic `ORDER BY` clauses",
     "I use parameterized queries for `WHERE` values, but I still interpolate `sort_col` directly into `ORDER BY {sort_col}`.",
     "SQL parameters cannot bind column or table identifiers. Validate `sort_col` and `sort_dir` against a strict hardcoded allowlist dictionary (`ALLOWED_SORTS = {'date': 'created_at', 'votes': 'vote_count'}`) and reject anything not in the map.",
     "Never rely on regex blacklists (like stripping `--` or `;`) to sanitize SQL—allowlisting is the only safe pattern for dynamic identifiers."),
    ("cybersecurity",
     "Implementing the Principle of Least Privilege with short-lived credentials",
     "Our CI/CD pipeline uses a single static admin API key that never expires and has full access to every environment.",
     "Replace static keys with **OIDC federation** (e.g., GitHub Actions OIDC -> AWS STS / GCP Workload Identity) that mints short-lived, scoped tokens valid only for a single workflow run and specific repository/branch.",
     "Audit IAM permissions quarterly using access analyzer logs to strip unused permissions automatically."),
    ("cybersecurity",
     "Understanding Supply Chain Attacks and pinning dependencies safely",
     "Running `npm install` or `pip install -r requirements.txt` pulled a newly compromised minor version of a transitive package.",
     "Commit lockfiles (`package-lock.json`, `uv.lock`, `poetry.lock`) with cryptographic hashes (`pip install --require-hashes`), run `npm ci` in CI, and enable automated vulnerability scanning (Dependabot, Trivy, or `pip-audit`).",
     "Wait 3–7 days before auto-merging non-security dependency updates (`minimumReleaseAge`) so malicious packages are usually caught and yanked first."),

    # ---------------- networking ----------------
    ("networking",
     "Understanding the TCP 3-way handshake and why `TIME_WAIT` sockets pile up",
     "Under heavy load, my proxy server runs out of ephemeral ports and `ss -tan` shows 25,000 connections in `TIME_WAIT`.",
     "`TIME_WAIT` (typically 60 seconds on Linux) is a normal TCP state on the side that actively closes a connection, preventing delayed packets from corrupting a new connection on the same 4-tuple. Fix port exhaustion by enabling HTTP keep-alive connection pooling instead of opening a new TCP connection per request.",
     "You can also widen the ephemeral port range (`net.ipv4.ip_local_port_range = 10240 65535`), but avoid enabling `tcp_tw_recycle` (removed in modern Linux kernels because it breaks NAT)."),
    ("networking",
     "Debugging DNS resolution issues with `dig` and understanding TTL caching",
     "I updated my domain's `A` record to a new server IP, but half my users are still hitting the old server 2 hours later.",
     "Recursive resolvers cache DNS records for the duration of the old record's **TTL** (Time To Live). Run `dig +trace example.com` to inspect the authoritative nameserver and `dig @8.8.8.8 example.com` to see the remaining cached TTL.",
     "Before a planned IP migration, lower the record's TTL to 60–300 seconds at least 24 hours in advance, perform the cutover, and raise the TTL back afterward."),
    ("networking",
     "Understanding CIDR notation and subnetting (`10.0.1.0/24` vs `/16`)",
     "I'm designing a cloud VPC and don't know how many usable IP addresses a `/24` or `/28` subnet actually provides.",
     "A `/N` prefix leaves `32 - N` host bits, giving $2^{32 - N}$ total IPs. A `/24` has 256 IPs (254 usable in standard networking, or 251 usable in AWS/Azure/GCP which reserve 5 IPs per subnet); a `/28` has 16 total IPs (11 usable in AWS).",
     "Always leave non-overlapping CIDR space between dev, staging, and prod VPCs (`10.10.0.0/16`, `10.20.0.0/16`, `10.30.0.0/16`) so VPC peering or VPNs won't conflict later."),
    ("networking",
     "Diagnosing packet loss and high latency with `mtr` instead of plain `ping` or `traceroute`",
     "Users report intermittent timeouts to our API, but a quick `ping` looks fine.",
     "Run `mtr -rwzbc 100 api.example.com` to combine `ping` and `traceroute` continuously. It shows per-hop packet loss, average latency, and worst-case jitter across 100 probes.",
     "Don't panic over packet loss at a single intermediate router if subsequent hops show 0% loss—many routers deprioritize ICMP replies (control-plane rate limiting) while forwarding normal traffic at full speed."),
    ("networking",
     "How TLS 1.3 reduces handshake latency compared to TLS 1.2",
     "Our mobile users on high-latency cellular networks spend 400+ ms just establishing HTTPS connections.",
     "TLS 1.3 completes a full encrypted handshake in **1-RTT** (one round-trip) instead of TLS 1.2's 2-RTT, removes legacy weak ciphers (CBC, RSA key exchange), and mandates forward secrecy (ECDHE).",
     "Enable **HTTP/2** or **HTTP/3 (QUIC)** alongside TLS 1.3 to multiplex requests and eliminate TCP head-of-line blocking on lossy mobile networks."),
    ("networking",
     "Layer 4 (TCP) vs Layer 7 (HTTP) load balancing",
     "Should I put an L4 Network Load Balancer or an L7 Application Load Balancer in front of my microservices?",
     "Use **L7 (HTTP/HTTPS)** when you need path/host-based routing (`/api` -> service A, `/web` -> service B), TLS termination, WAF rules, or header inspection. Use **L4 (TCP/UDP)** for ultra-low-latency passthrough, non-HTTP protocols (PostgreSQL, MQTT, gRPC with client-side TLS), or static IP requirements.",
     "Remember that L7 proxies terminate the client connection, so your backend must read `X-Forwarded-For` or `Forwarded` (only from trusted proxies) to see the real client IP."),

    # ---------------- cloud ----------------
    ("cloud",
     "Serving private S3 objects securely using Pre-Signed URLs instead of proxying through your API",
     "My FastAPI server downloads 50 MB PDFs from S3 and streams them to users, maxing out API memory and bandwidth.",
     "Generate a short-lived **Pre-Signed URL** (`s3.generate_presigned_url('get_object', Params={...}, ExpiresIn=300)`) and return it to the client. The browser downloads directly from S3 (or CloudFront) while the bucket stays 100% private.",
     "Use the exact same pattern (`put_object` pre-signed URLs or `POST` policies with content-length limits) for direct-to-S3 file uploads."),
    ("cloud",
     "Avoiding surprise cloud NAT Gateway and data egress bills",
     "Our AWS bill jumped by $800/month under 'NAT Gateway Data Processing' even though our EC2 instances are tiny.",
     "Private-subnet instances talking to S3 or DynamoDB over the public internet route through the NAT Gateway, which charges per GB processed. Create free **Gateway VPC Endpoints** for S3 and DynamoDB so traffic stays on the internal AWS network at zero per-GB cost.",
     "Also watch cross-AZ data transfer charges—keep chatty services or read replicas in the same Availability Zone when extreme multi-AZ traffic isn't required."),
    ("cloud",
     "Designing serverless functions (AWS Lambda / Cloud Run) to minimize cold starts",
     "The first request to my Lambda function after 10 minutes of idle time takes 3.5 seconds instead of 80 ms.",
     "Keep deployment bundles small (strip unused libraries, avoid heavy ORMs), initialize database clients and SDKs *outside* the handler function so they are reused across warm invocations, and prefer fast-starting runtimes (Python, Node.js, Go, Rust).",
     "For latency-critical endpoints, configure **Provisioned Concurrency** (Lambda) or `min-instances: 1` (Cloud Run) to keep warm instances ready."),
    ("cloud",
     "Choosing between Object Storage (S3), Block Storage (EBS), and File Storage (EFS)",
     "I'm deploying a stateful web app on the cloud and unsure where to store user uploads vs database files.",
     "Use **Object Storage (S3/GCS)** for user uploads, backups, and static assets (cheap, infinite scale, accessed via HTTP). Use **Block Storage (EBS/Persistent Disk)** for databases needing low-latency random I/O attached to a single VM. Use **Network File Storage (EFS/Filestore)** only when multiple servers must mount a shared POSIX filesystem simultaneously.",
     "Configure S3 Lifecycle Rules to automatically transition older logs/backups to Infrequent Access or Glacier after 30–90 days."),
    ("cloud",
     "Implementing Multi-Region vs Multi-AZ architecture realistically",
     "Management asked for '99.99% uptime' and I'm debating whether we need an active-active multi-region database.",
     "Start with **Multi-AZ** within a single region (load balancer + stateless app across 3 AZs + Multi-AZ managed database). It survives a full data-center outage with minimal latency and operational complexity. Only move to **Multi-Region** if you have strict regulatory data residency or truly need to survive a full regional cloud outage.",
     "True active-active multi-region writes introduce distributed conflict resolution and cross-continent latency—most teams do better with active-passive warm standby + automated failover drills."),

    # ---------------- cicd ----------------
    ("cicd",
     "Speeding up GitHub Actions workflows with dependency caching and path filters",
     "Our CI pipeline takes 14 minutes on every PR, even when someone only edits `README.md`.",
     "Add `paths-ignore: ['**.md', 'docs/**']` on `pull_request` triggers, enable built-in caching (`actions/setup-python` with `cache: 'pip'`, `actions/setup-node` with `cache: 'npm'`), and run linting, unit tests, and security scans as **parallel jobs** instead of sequentially.",
     "Add `concurrency: { group: ${{ github.workflow }}-${{ github.ref }}, cancel-in-progress: true }` so pushing a new commit automatically cancels the outdated CI run."),
    ("cicd",
     "Blue-Green vs Canary deployments for safer production releases",
     "We want to deploy 10 times a day without breaking all users at once when a bug slips past tests.",
     "**Blue-Green** runs two identical environments and flips 100% of traffic from Blue to Green (instant rollback by flipping back). **Canary** routes 1–5% of live traffic to the new version first, monitors error rates/latency, and gradually ramps to 100%.",
     "Pair either strategy with **Feature Flags** so you decouple *code deployment* from *feature release* and can kill a buggy feature in 1 second without redeploying."),
    ("cicd",
     "Running database schema migrations safely in CI/CD without downtime (Expand-and-Contract)",
     "Renaming a column in our migration script immediately crashes the old app containers still running during a rolling deploy.",
     "Use the **Expand-and-Contract** pattern across 3 deploys: (1) *Expand*—add the new column and dual-write to both old and new; (2) backfill existing rows and switch reads to the new column; (3) *Contract*—drop the old column once no running container references it.",
     "Never run destructive `DROP COLUMN` or table-locking `ALTER TABLE` statements in the same deploy that changes application code."),
    ("cicd",
     "Building once and promoting the exact same artifact across dev, staging, and prod",
     "Our pipeline rebuilds the Docker image separately for staging and production, and production broke because a dependency updated in between.",
     "Build and tag the container image **once** per commit (e.g., `myapp:sha-9f3a21c`), push it to your registry, and promote that exact immutable image digest through dev -> staging -> prod, injecting only environment-specific config at runtime.",
     "Sign your container images with `cosign` (Sigstore) and verify signatures in your cluster before deployment."),

    # ---------------- typescript ----------------
    ("typescript",
     "Using Discriminated Unions in TypeScript to make invalid states unrepresentable",
     "My React state has `{ loading: boolean, data?: User, error?: string }`, and I keep forgetting to clear `error` when `data` arrives.",
     "Model state as a discriminated union: `type State = { status: 'loading' } | { status: 'success'; data: User } | { status: 'error'; error: string }`. Switching on `state.status` lets TypeScript narrow the exact available fields automatically.",
     "Add a `default: const _exhaustive: never = state;` check so the compiler errors immediately if you add a new union variant and forget to handle it."),
    ("typescript",
     "Why `unknown` is always safer than `any` in TypeScript",
     "My team uses `any` for API responses and `catch (err: any)` blocks, which silently disables type checking everywhere those values flow.",
     "Use `unknown` instead of `any`. TypeScript forces you to narrow `unknown` (via `typeof`, `instanceof Error`, or a runtime schema validator like **Zod**) before accessing any properties.",
     "Enable `\"strict\": true` and `\"noUncheckedIndexedAccess\": true` in `tsconfig.json` to catch undefined array/object lookups at compile time."),
    ("typescript",
     "Validating external API payloads at runtime with Zod and inferring TypeScript types",
     "TypeScript interfaces disappear at runtime, so a surprise `null` from a third-party API still crashes my frontend.",
     "Define a Zod schema (`const UserSchema = z.object({ id: z.number(), email: z.string().email() })`), parse incoming JSON with `UserSchema.parse(data)`, and derive the static type with `type User = z.infer<typeof UserSchema>`.",
     "This gives you a single source of truth for both compile-time types and runtime validation at your system boundaries."),
    ("typescript",
     "Using Utility Types (`Pick`, `Omit`, `Partial`, `Record`, `ReturnType`) to avoid duplicating interfaces",
     "I have three nearly identical interfaces: `User`, `CreateUserInput`, and `UpdateUserInput`.",
     "Derive them from one base type: `type CreateUserInput = Omit<User, 'id' | 'createdAt'>` and `type UpdateUserInput = Partial<CreateUserInput>`. Whenever `User` changes, all derived types stay in sync automatically.",
     "Use `satisfies` (TypeScript 4.9+) on config objects to validate shape against a type without losing the narrow literal types of individual keys."),

    # ---------------- react ----------------
    ("react",
     "Avoiding unnecessary `useEffect` calls for derived state in React",
     "I store `items` and `filteredItems` in separate `useState` hooks and sync them with `useEffect`, causing extra re-renders and stale UI flashes.",
     "Never mirror props or state into another `useState` via `useEffect`. Compute `const filteredItems = items.filter(...)` directly during render (wrapping in `useMemo` only if the computation is genuinely expensive).",
     "Reserve `useEffect` strictly for synchronizing with *external systems* (subscriptions, timers, DOM APIs, non-React widgets)."),
    ("react",
     "Why array index `key={i}` breaks React lists when items are reordered or deleted",
     "When a user deletes the second row of my editable form list, the input values shift onto the wrong rows.",
     "React uses `key` to match DOM/component state across renders. If you use array index `i`, deleting item 1 shifts item 2 into index 1, so React reuses item 1's internal component state. Always use a stable, unique ID (`key={item.id}`).",
     "Never generate keys on the fly with `key={Math.random()}` either—that forces React to unmount and remount every child on every render."),
    ("react",
     "Managing server state with TanStack Query (React Query) instead of manual `useEffect` + `useState`",
     "Every component in my app repeats the same boilerplate for `loading`, `error`, `fetch()`, caching, and race-condition cleanup.",
     "Use `useQuery({ queryKey: ['question', id], queryFn: () => fetchQuestion(id) })`. TanStack Query handles request deduplication, background refetching, caching, retries, and stale-while-revalidate automatically.",
     "Keep React Context / Zustand for *client UI state* (theme, modals, sidebar) and let TanStack Query own *server state*."),
    ("react",
     "Preventing wasted re-renders in React without prematurely wrapping everything in `useMemo`",
     "Typing in a search input at the top of my page feels laggy because it re-renders a huge chart component below it.",
     "First, **push state down** into a smaller child component (`<SearchInput />`) so typing only re-renders the input, not the whole page. Alternatively, pass expensive children as `props.children` so parent state updates don't re-render them.",
     "Profile with React DevTools Profiler before adding `React.memo`/`useCallback`—structural composition fixes 90% of render bottlenecks cleanly."),

    # ---------------- rust ----------------
    ("rust",
     "Understanding Ownership, Borrowing (`&T` vs `&mut T`), and why the Borrow Checker rejects data races",
     "Rust refuses to compile when I hold an immutable reference to a `Vec` element while calling `vec.push(...)`.",
     "Rust enforces **aliasing XOR mutability**: you can have either many shared immutable references (`&T`) *or* exactly one mutable reference (`&mut T`) at a time. Calling `vec.push()` might reallocate the vector's buffer, invalidating any existing `&T` pointer—the borrow checker prevents that use-after-free at compile time.",
     "Shorten the scope of immutable borrows (Non-Lexical Lifetimes end a borrow at its last use) or clone/index by `usize` when mutating collections."),
    ("rust",
     "Ergonomic error handling in Rust with `Result`, `?`, `thiserror`, and `anyhow`",
     "My code is cluttered with `.unwrap()` calls that panic in production, or verbose `match` blocks on every `Result`.",
     "Propagate errors cleanly with the `?` operator. Use **`thiserror`** in libraries to define structured, typed error enums (`#[derive(Error, Debug)]`), and **`anyhow`** in applications (`anyhow::Result<T>`) to attach human-readable context via `.context(\"failed to load config\")?`.",
     "Reserve `.unwrap()` / `.expect()` strictly for tests or invariants that are mathematically guaranteed to hold."),
    ("rust",
     "Choosing between `String` and `&str` in Rust function signatures",
     "I wrote `fn greet(name: String)` and now callers with string literals (`\"Alice\"`) have to write `greet(\"Alice\".to_string())`.",
     "Accept `&str` in function parameters whenever you only need to read the string—`&String` coerces automatically to `&str` via `Deref`, so both `String` and string literals work with zero allocation.",
     "Return `String` when the function constructs new owned text, or `Cow<'a, str>` when it usually borrows and only occasionally allocates."),
    ("rust",
     "Avoiding blocking the Tokio async runtime in Rust",
     "My Axum/Tokio web server stalls for all users whenever one endpoint runs bcrypt hashing or heavy synchronous file I/O.",
     "Tokio runs async tasks cooperatively on a small pool of worker threads; blocking a thread for >100 µs starves other tasks. Offload CPU-heavy or blocking sync work to Tokio's blocking thread pool with `tokio::task::spawn_blocking(move || ...).await`.",
     "For heavy CPU compute pools (like image processing or ML inference), consider offloading to a dedicated `rayon` thread pool bridged via a `tokio::sync::oneshot` channel."),

    # ---------------- golang ----------------
    ("golang",
     "Preventing goroutine leaks with `context.Context` cancellation",
     "My Go service's memory and goroutine count (`runtime.NumGoroutine()`) grow steadily over days until it OOMs.",
     "Whenever you spawn a goroutine that waits on a channel or network call, pass a `ctx context.Context` and `select` on `<-ctx.Done()` so the goroutine exits cleanly when the caller cancels or times out.",
     "Always call `defer cancel()` immediately after `ctx, cancel := context.WithTimeout(...)` so timers are released even on early returns."),
    ("golang",
     "Using `errgroup.Group` in Go for concurrent tasks with error propagation",
     "I'm manually coordinating `sync.WaitGroup`, mutexes, and error channels just to call 3 microservices in parallel.",
     "Use `g, ctx := errgroup.WithContext(parentCtx)` from `golang.org/x/sync/errgroup`. Launch each call with `g.Go(func() error { ... })` and wait with `if err := g.Wait(); err != nil`—the first error cancels `ctx` for all sibling goroutines automatically.",
     "Call `g.SetLimit(10)` to cap concurrency so you don't overwhelm downstream APIs or databases."),
    ("golang",
     "Wrapping and inspecting errors idiomatically in Go (`%w`, `errors.Is`, `errors.As`)",
     "Checking `err == sql.ErrNoRows` stopped working after a helper function wrapped the error with `fmt.Errorf`.",
     "Wrap errors using `%w` (`fmt.Errorf(\"load user %d: %w\", id, err)`) and check them with `errors.Is(err, sql.ErrNoRows)` (for sentinel errors) or `errors.As(err, &targetErr)` (for custom error types), which unwrap the full error chain.",
     "Avoid `%w` at public API boundaries if you don't want callers coupling to internal dependency error types—use `%v` there instead."),
    ("golang",
     "Detecting Go data races before production with `go test -race`",
     "My concurrent map access works fine on my laptop but occasionally panics in production with `concurrent map writes`.",
     "Run `go test -race ./...` in CI on every PR. Go's built-in race detector instruments memory accesses at runtime and pinpoints the exact two goroutines and lines racing on shared state.",
     "Protect shared maps with `sync.RWMutex` (or `sync.Map` for read-mostly, write-once caches) and prefer passing ownership over channels when practical."),

    # ---------------- system-design ----------------
    ("system-design",
     "Implementing the Transactional Outbox Pattern to keep databases and message brokers in sync",
     "My service writes an order to PostgreSQL and then publishes `OrderCreated` to Kafka—if the app crashes between the two, Kafka never gets the event.",
     "Insert the event into an `outbox` table *inside the same PostgreSQL transaction* as the order. A separate relay worker (or Debezium CDC) reads unpublished rows from `outbox`, publishes them to Kafka, and marks them sent.",
     "Because the relay guarantees **at-least-once** delivery, make all downstream Kafka consumers **idempotent** (deduplicating by `event_id`)."),
    ("system-design",
     "Using Circuit Breakers and Exponential Backoff with Jitter to stop cascading failures",
     "When our payment service slows down, retries from 50 API pods flood it with 10x traffic and take down the entire platform.",
     "Add **exponential backoff with full jitter** on retries (so clients don't retry in synchronized waves) and wrap downstream calls in a **Circuit Breaker** that trips open after consecutive failures, failing fast for a cooldown window before testing recovery.",
     "Set explicit **connect and read timeouts** on every outbound HTTP/DB client—default infinite timeouts are the #1 cause of thread-pool exhaustion."),
    ("system-design",
     "Choosing between Offset Pagination, Cursor Pagination, and Search-After for large feeds",
     "Our social feed shows duplicate posts when a new post is inserted while the user scrolls to page 2.",
     "Offset pagination (`OFFSET 20`) shifts every row down when new items arrive at the top. Switch to **Cursor (Keyset) Pagination** keyed on `(created_at, id)` so the next page always starts strictly after the last item the user saw.",
     "Reserve offset pagination only for small admin tables where jumping directly to 'Page 7' is a hard UI requirement."),
    ("system-design",
     "Scaling read-heavy workloads with Read Replicas and handling Replication Lag",
     "After a user updates their profile, the immediate redirect to `/profile` still shows their old name because it read from a lagging replica.",
     "Route writes to the primary DB and heavy analytics/feed reads to replicas, but implement **read-your-own-writes** consistency: after a user writes, route that user's reads to the primary for the next 5–10 seconds (or pass the write's LSN/timestamp).",
     "Never run financial balance checks or inventory reservations against an asynchronous read replica."),

    # ---------------- kafka ----------------
    ("kafka",
     "Understanding Kafka Partitions, Consumer Groups, and ordering guarantees",
     "My Kafka topic has 3 partitions, I spun up 6 consumer instances in the same group, and 3 of them sit completely idle.",
     "Within a single Consumer Group, each partition is assigned to **at most one** consumer at a time—so max parallelism equals the number of partitions. Kafka also guarantees strict message ordering *only within a single partition*, so always set the message key (e.g., `user_id` or `order_id`) to keep related events ordered.",
     "Choose partition counts carefully upfront; increasing partitions later changes `hash(key) % num_partitions` and temporarily breaks key-to-partition affinity."),
    ("kafka",
     "Handling poison-pill messages in Kafka with Dead Letter Queues (DLQ)",
     "One malformed JSON event in our Kafka topic causes our consumer to crash and restart forever, blocking all newer messages in that partition.",
     "Distinguish transient errors (network timeout -> retry with backoff) from permanent errors (deserialization/validation failure -> publish the raw payload + error metadata to a `<topic>.dlq` topic and commit the offset).",
     "Alert on any non-zero message count in your DLQ and build a simple replay tool once you fix the bug."),
    ("kafka",
     "Tuning Kafka producer `acks=all` and `enable.idempotence=true` for zero data loss",
     "During a broker restart, a few Kafka messages were silently lost even though the producer didn't throw an error.",
     "Configure `acks=all` (wait for all in-sync replicas), `enable.idempotence=true` (prevents duplicates on producer retries), and topic-level `min.insync.replicas=2` with `replication.factor=3`.",
     "This combination gives strong durability without sacrificing throughput when paired with `linger.ms=5` and `compression.type=lz4`."),

    # ---------------- terraform ----------------
    ("terraform",
     "Configuring Remote State and State Locking in Terraform for teams",
     "Two engineers ran `terraform apply` at the same time from their laptops and corrupted our infrastructure state.",
     "Never store `terraform.tfstate` in Git or on local disks. Configure a **remote backend** (e.g., S3 with native lockfile `use_lockfile = true` or DynamoDB locking, or GCS/Terraform Cloud) so state is encrypted, versioned, and locked automatically during applies.",
     "Always run `terraform plan` in CI on pull requests and `terraform apply` only from the protected `main` branch."),
    ("terraform",
     "Using `for_each` instead of `count` in Terraform to prevent accidental resource destruction",
     "Removing the first item from a list variable used with `count = length(var.buckets)` caused Terraform to destroy and recreate all remaining buckets.",
     "`count` indexes resources by integer position (`[0]`, `[1]`, `[2]`), so removing index 0 shifts every subsequent item. Use `for_each = toset(var.buckets)` so resources are keyed by stable string names (`[\"logs\"]`, `[\"uploads\"]`) and only the removed item is touched.",
     "If you need to refactor a resource address without destroying it, use a `moved { from = ... to = ... }` block."),
    ("terraform",
     "Avoiding hardcoded secrets in Terraform state files",
     "I passed a database password via `TF_VAR_db_password`, and then realized it is still stored in plaintext inside `terraform.tfstate`.",
     "Marking a variable `sensitive = true` hides it from CLI logs, *not* from the state file. Encrypt your state bucket with KMS, restrict IAM access to it tightly, and let cloud-native secret managers (AWS Secrets Manager / `manage_master_user_password = true` on RDS) generate and rotate secrets outside Terraform state.",
     "Use ephemeral values (`ephemeral` resources/variables in Terraform 1.10+) when you need short-lived credentials that must never be persisted to state."),

    # ---------------- observability ----------------
    ("observability",
     "Structuring logs as JSON with Correlation IDs (`trace_id`) across microservices",
     "When a checkout fails, I have to grep plain-text logs across 4 services and guess which lines belong to the same user request.",
     "Emit structured JSON logs (`structlog` in Python, `slog` in Go, `pino` in Node) and propagate a W3C `traceparent` / `X-Request-ID` header across every HTTP/queue call so every log line includes `trace_id` and `user_id`.",
     "Never log PII, passwords, or raw JWTs—add a redaction processor in your logger configuration."),
    ("observability",
     "Monitoring the Four Golden Signals and avoiding high-cardinality Prometheus labels",
     "Our Prometheus server OOM-crashed after someone added `user_id` as a label on `http_requests_total`.",
     "Every unique label value combination creates a new time series in Prometheus. Keep labels low-cardinality (`method`, `route_template`, `status_class`), never put `user_id`, `email`, or raw URLs with IDs into metric labels, and focus alerts on the **Four Golden Signals**: Latency (p95/p99), Traffic, Errors, and Saturation.",
     "Use **Distributed Tracing** (OpenTelemetry -> Tempo/Jaeger) or structured logs when you need to filter by high-cardinality fields like `user_id` or `order_id`."),
    ("observability",
     "Why p95 and p99 latency matter far more than average latency",
     "Our dashboard shows a healthy 45 ms average response time, yet users complain the site feels sluggish.",
     "Averages hide tail latency: if 95% of requests take 20 ms and 5% take 520 ms, the average is still 45 ms, yet 1 in 20 requests feels broken (and a page making 10 API calls has a 40% chance of hitting at least one slow call). Track **p50, p95, and p99** with histograms (`histogram_quantile`).",
     "Use native histograms in Prometheus / OpenTelemetry to get accurate tail percentiles without manually tuning bucket boundaries."),

    # ---------------- testing ----------------
    ("testing",
     "Writing reliable integration tests with Testcontainers instead of mocking the database",
     "All my unit tests passed because I mocked SQLAlchemy, yet the real PostgreSQL query crashed in production with a syntax error.",
     "Use **Testcontainers** (available for Python, Java, Node, Go) to spin up a real, disposable PostgreSQL/Redis/MongoDB Docker container during your test suite. You test actual SQL queries, indexes, and transactions in seconds with zero mock drift.",
     "Keep a fast unit test layer for pure business logic, and run Testcontainers integration tests for repositories, migrations, and API endpoints."),
    ("testing",
     "Eliminating flaky end-to-end tests in Playwright by avoiding `sleep()` calls",
     "Our Playwright E2E suite fails randomly 15% of the time in CI because `waitForTimeout(2000)` isn't always long enough.",
     "Never use fixed sleeps. Use Playwright's **auto-waiting locators** and web-first assertions (`await expect(page.getByRole('button', { name: 'Submit' })).toBeVisible()`), which poll smartly until the condition is met or the timeout expires.",
     "Prefer user-facing locators (`getByRole`, `getByLabel`, `getByTestId`) over brittle CSS/XPath selectors like `.div > span:nth-child(3)`."),

    # ---------------- nginx ----------------
    ("nginx",
     "Configuring Nginx as a reverse proxy with proper headers, timeouts, and WebSocket support",
     "Behind Nginx, my backend sees `127.0.0.1` as every user's IP, and WebSocket connections fail with `400 Bad Request`.",
     "Forward client metadata with `proxy_set_header Host $host;`, `proxy_set_header X-Real-IP $remote_addr;`, `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`, and `proxy_set_header X-Forwarded-Proto $scheme;`. For WebSockets, add `proxy_http_version 1.1;`, `proxy_set_header Upgrade $http_upgrade;`, and `proxy_set_header Connection \"upgrade\";`.",
     "Also set `client_max_body_size 25M;` if users upload files larger than Nginx's default 1 MB limit (which otherwise returns `413 Request Entity Too Large`)."),
    ("nginx",
     "Enabling Gzip/Brotli compression and rate limiting at the Nginx edge",
     "A scraper bot is hammering `/api/search` 50 times per second and saturating my application workers.",
     "Define a shared rate-limit zone in `http {}`: `limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;` and apply `limit_req zone=api_limit burst=20 nodelay; limit_req_status 429;` inside the `/api/` location block.",
     "Enable `gzip on;` (or `brotli on;`) for JSON, CSS, JS, and SVG responses to cut payload sizes by 60–80%, while skipping already-compressed formats like JPEG/PNG/MP4."),
]

FIRST_NAMES = [
    # Moroccan / Amazigh
    "amine", "yassine", "sara", "imane", "omar", "salma", "hamza",
    "khadija", "mehdi", "nour", "ayoub", "hajar", "reda", "zineb",
    "anas", "meryem", "ilyas", "soufiane", "ghita", "badr", "rania",
    "walid", "lamia", "karim", "oumaima", "tarik", "nadia", "youssef",
    "chaimae", "bilal", "asmae", "driss", "fatima", "hicham", "loubna",
    "mounir", "siham", "adil", "kenza", "rachid", "massin", "tiziri",
    "amayas", "tassadit", "lounis", "yuba", "dihya", "axxam", "tanina",
    "ayman", "sanaa", "marouane", "ikram", "hind", "ismail", "nawal",
    "soukaina", "abdelilah", "hafsa", "mohamed", "abir", "salmane",

    # Middle Eastern / Arab
    "zayd", "tariq", "faisal", "khalid", "samir", "rami", "tamer",
    "jad", "fadi", "mazen", "laith", "qasim", "zaid", "mustafa",
    "layla", "dana", "yasmin", "farah", "leena", "maya", "reem",
    "dalia", "samar", "ranim", "jana", "malak", "ghada", "hussein",
    "bassam", "nasser", "ammar", "waleed", "salim", "marwa",

    # African
    "kwame", "kofi", "amani", "chinedu", "olumide", "temitope",
    "olu", "tendai", "tafadzwa", "thabo", "sipho", "sibusiso",
    "kagiso", "bongani", "mandla", "lerato", "nomsa", "zanele",
    "ayodele", "adaeze", "chioma", "ngozi", "ifeoma", "chiamaka",
    "amara", "kamau", "juma", "baraka", "nala", "zuri", "imani",
    "makena", "kendi", "wanjiku", "abena", "akosua", "efua",

    # European
    "alexander", "oliver", "lucas", "ethan", "liam", "noah",
    "sebastian", "felix", "leon", "matteo", "enzo", "gabriel",
    "julian", "theodore", "henry", "arthur", "hugo", "maximilian",
    "frederik", "oscar", "leo", "milan", "adrian", "nicolas",
    "elena", "sofia", "isabella", "amelia", "chloe", "clara",
    "alice", "victoria", "valentina", "camille", "juliette",
    "margot", "ines", "celine", "elise", "freya", "astrid",
    "greta", "matilda", "anna", "emilia", "lena", "lucia",
    "carla", "beatrice", "irene", "bianca", "giulia", "paula",

    # South Asian
    "aarav", "vivaan", "arjun", "rohan", "kabir", "ishaan",
    "aditya", "rahul", "vikram", "dev", "krishna", "sanjay",
    "ananya", "priya", "isha", "kavya", "diya", "meera",
    "anika", "saanvi", "aisha", "zara", "riya", "neha",
    "tanvi", "sanya", "kiara", "nisha", "maya", "arjun",
    "farhan", "imran", "zain", "hamid", "sana", "ayesha",

    # East Asian
    "wei", "jun", "hao", "ming", "chen", "liang", "kai",
    "yuki", "haruto", "ren", "sota", "takumi", "hiro",
    "akira", "naoki", "kenji", "mei", "sakura", "hina",
    "aiko", "yuna", "rin", "haruka", "minji", "jiwoo",
    "seojun", "hyun", "jimin", "sumin", "soyeon", "yuna",
    "xiaoyu", "ling", "jing", "yan", "tao", "lin",

    # Southeast Asian
    "putri", "budi", "dimas", "rizky", "andika", "ayu",
    "siti", "farid", "hafiz", "danial", "amirul", "aisyah",
    "nurul", "intan", "melati", "nguyen", "minh", "duc",
    "anh", "linh", "thao", "bao", "phuong", "quang",

    # Latin American
    "diego", "mateo", "santiago", "sebastian", "alejandro",
    "emiliano", "thiago", "rafael", "miguel", "carlos",
    "fernando", "luciano", "tomas", "joaquin", "bruno",
    "valeria", "camila", "soledad", "martina", "antonella",
    "luciana", "daniela", "gabriela", "mariana", "renata",
    "isabela", "paola", "ximena", "andrea", "elisa",

    # North American / International
    "james", "william", "benjamin", "jack", "mason", "logan",
    "carter", "owen", "wyatt", "dylan", "nathan", "caleb",
    "isaac", "aaron", "jason", "ethan", "grace", "emma",
    "olivia", "ava", "mia", "lily", "ella", "scarlett",
    "madison", "harper", "stella", "ruby", "zoe", "naomi",
    "brooklyn", "jasmine", "autumn", "skylar", "riley",
    "quinn", "blake", "jordan", "morgan", "taylor"
]

ALL_TAGS = ["python", "mongodb", "redis", "neo4j", "docker", "sql", "javascript",
            "machine-learning", "linux", "git", "api", "pandas", "kubernetes", "java",
            "streamlit", "react", "algorithms", "security", "networking", "testing"]


def build_data(user_start=1, q_start=1, a_start=1, taken_usernames=(),
               existing_users=None, skip_titles=()):
    """
    existing_users: seeded users already in Mongo ({_id, username, tags_expertise}).
                    When given, no new users are created and they are reused as authors.
    skip_titles   : question titles already in Mongo (skipped, so reruns never duplicate).
    Returns (new_users, questions, answers, all_users_used).
    """
    now = datetime.now(timezone.utc)

    new_users = []
    if existing_users:
        users = list(existing_users)
    else:
        taken = set(taken_usernames)
        for i, name in enumerate(FIRST_NAMES, start=user_start):
            uname = f"{name}_{random.randint(10, 99)}"
            while uname in taken:
                uname = f"{name}_{random.randint(10, 999)}"
            taken.add(uname)
            new_users.append({
                "_id": i,
                "seed": "v2",
                "username": uname,
                "email": f"{name}{i}@example.com",
                "tags_expertise": random.sample(ALL_TAGS, k=random.randint(1, 3)),
                "joined_at": now - timedelta(days=random.randint(60, 400)),
            })
        users = new_users

    questions, answers = [], []
    aid = a_start
    todo = [i for i, q in enumerate(QUESTIONS) if q[1] not in skip_titles]
    random.shuffle(todo)

    for qid, idx in enumerate(todo, start=q_start):
        tags_s, title, body, a1, a2 = QUESTIONS[idx]
        tags = tags_s.split(",")
        created = now - timedelta(days=random.randint(2, 90), minutes=random.randint(0, 1439))
        age_days = max(1, (now - created).days)
        author = random.choice(users)["_id"]
        questions.append({
            "_id": qid,
            "title": title,
            "body": body,
            "tags": tags,
            "author_id": author,
            "created_at": created,
            "views": int(random.uniform(0.5, 1.0) * age_days * random.randint(5, 25)),
        })

        experts = [u["_id"] for u in users
                   if tags[0] in u.get("tags_expertise", []) and u["_id"] != author]
        pool = [u["_id"] for u in users if u["_id"] != author]
        used = set()
        batch = []
        for rank, text in enumerate((a1, a2)):
            candidates = [u for u in (experts if experts and random.random() < 0.8 else pool)
                          if u not in used] or [u for u in pool if u not in used]
            who = random.choice(candidates)
            used.add(who)
            votes = int(random.expovariate(1 / 9)) if rank == 0 else int(random.expovariate(1 / 4))
            batch.append({
                "_id": aid,
                "question_id": qid,
                "author_id": who,
                "body": text,
                "created_at": created + timedelta(minutes=random.randint(10, 4000)),
                "accepted": False,
                "votes": votes,
            })
            aid += 1
        best = max(batch, key=lambda a: a["votes"])
        if random.random() < 0.65:
            best["accepted"] = True
        answers.extend(batch)

    return new_users, questions, answers, users


def main():
    import sys
    import bcrypt
    import redis
    import chromadb
    from pymongo import MongoClient

    reset = "--reset" in sys.argv

    db = MongoClient("mongodb://localhost:27018")["qa_platform"]
    r = redis.Redis(host="localhost", port=6379, decode_responses=True)
    client = chromadb.HttpClient(host="localhost", port=8000)

    if reset:
        for c in ("users", "questions", "answers"):
            db[c].drop()
        for pattern in ("answer:*", "leaderboard"):
            for key in r.scan_iter(pattern):
                r.delete(key)
        try:
            client.delete_collection("qa_questions")
        except Exception:
            pass
        new_users, questions, answers, users = build_data()
    else:
        def next_id(col):
            top = col.find_one({"_id": {"$type": ["int", "long"]}}, sort=[("_id", -1)])
            return top["_id"] + 1 if top else 1

        seeded = list(db.users.find({"seed": "v2"}, {"username": 1, "tags_expertise": 1}))
        skip = {q["title"] for q in db.questions.find({}, {"title": 1})}
        taken = {u["username"] for u in db.users.find({}, {"username": 1})}
        new_users, questions, answers, users = build_data(
            next_id(db.users), next_id(db.questions), next_id(db.answers),
            taken, seeded or None, skip,
        )
        if not questions:
            print("Nothing new to add: every seed question is already in Mongo. Use --reset to rebuild.")
            return

    # ---- Mongo ----
    if new_users:
        hashed = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt())
        for u in new_users:
            u["password"] = hashed      # same hash reused: all seeded users share the password
        db.users.insert_many(new_users)
    db.questions.insert_many(questions)
    db.answers.insert_many(answers)
    db.users.create_index("username", unique=True)
    db.questions.create_index("tags")
    db.questions.create_index("author_id")
    db.questions.create_index([("created_at", -1)])
    db.answers.create_index("question_id")
    db.answers.create_index("author_id")

    # ---- Redis (votes + leaderboard), additive ----
    username_of = {u["_id"]: u["username"] for u in users}
    pipe = r.pipeline()
    for a in answers:
        pipe.set(f"answer:{a['_id']}:votes", a["votes"])
        pipe.zincrby("leaderboard", a["votes"], username_of[a["author_id"]])
    pipe.execute()

    # ---- Chroma (semantic search on titles), upsert only ----
    col = client.get_or_create_collection("qa_questions", metadata={"hnsw:space": "cosine"})
    col.upsert(
        ids=[str(q["_id"]) for q in questions],
        documents=[q["title"] for q in questions],
    )

    print(f"added users={len(new_users)} questions={len(questions)} answers={len(answers)}")
    print(f"mongo questions total={db.questions.count_documents({})}  chroma count={col.count()}")
    print(f"login with any seeded username and password '{PASSWORD}'")


if __name__ == "__main__":
    main()