## v0.14.0 (2026-04-12)

### Feat

- **audit**: add structured audit log fields and API endpoints (#111)
- **company**: add resource counts to company responses (#110)

### Fix

- **includes**: exclude archived children from detail responses (#109)
- fix is_archived

## v0.13.3 (2026-04-10)

### Fix

- **error-handling**: convert tortoise errors to RFC 9457 responses (#108)
- **character-trait**: improve error messageas

## v0.13.2 (2026-04-09)

### Fix

- **character**: prefetch gift_tribe and gift_auspice for full sheet (#107)
- **user**: add discord avatar_url

## v0.13.1 (2026-04-09)

### Fix

- **saq**: close Tortoise connections after scheduled purge task (#105)

## v0.13.0 (2026-04-09)

### Feat

- **user-lookup**: add cross-company user lookup endpoint (#104)

## v0.12.0 (2026-04-08)

### Feat

- **user**: harden user controller with role hierarchy, DEACTIVATED role, and last-admin protection (#103)
- **rate-limit**: add per-route limits for abuse-prone endpoints (#102)
- **company**: add permission_recoup_xp setting (#99)
- add include query param to book, chapter, and user detail endpoints (#98)

### Fix

- **notes**: scope note access by parent to prevent IDOR (#101)
- **docker**: install postgresql-client-18 from PGDG repo (#97)

### Refactor

- **company**: make CompanyResponse.settings non-optional (#100)

## v0.11.0 (2026-04-06)

### Feat

- **backup**: add daily PostgreSQL backup SAQ task with S3 retention (#96)
- **middleware**: add proxy headers middleware for real client IP (#95)

## v0.10.0 (2026-04-06)

### Feat

- migrate database from MongoDB to PostgreSQL (#92)

### Fix

- **docker**: resolve PostgreSQL startup and migration issues (#94)

### Refactor

- stop auto-computing Willpower trait (#93)

## v0.9.0 (2026-03-31)

### Feat

- **middleware**: add request ID middleware (#87)
- **config**: harden app config (#86)
- **blueprints**: flatten section/category/subcategory endpoints (#85)
- **traits**: denormalize parent names into child documents
- **dictionary**: replace is_global with source_type/source_id (#84)
- **traits**: add count-based cost model for rituals and gifts (#83)
- **migrate**: add database migration script (#80)
- **trait**: add is_rollable filter to trait queries (#78)
- **trait**: count-based gift xp calculation (#76)
- **trait**: prevent adding gifts without minimum renown (#75)
- **sheet**: filter werewolf available gifts by tribe and auspice
- **user**: compute discord avatar_url as a derived field (#74)
- migrate werewolf gifts/rites to trait model with gift_attributes (#73)
- **server**: enable gzip response compression (#72)
- **scheduled-tasks**: purge temporary characters and orphaned traits (#70)
- **character**: add bulk assign traits endpoint (#69)
- **character**: create, list, and patch temporary characters (#68)
- **character**: sync concept_name from CharacterConcept on save (#67)
- **character**: available traits and CharacterSheetService extraction (#66)
- **character**: add id fields to full sheet DTOs (#65)
- **character**: add full character sheet endpoint (#64)
- **blueprint**: add subcategory endpoints and hierarchy navigation (#63)
- **traits**: migrate edges to trait system with subcategories (#62)
- **chargen**: add chargen session persistence and retrieval endpoints (#59)
- **user**: add lifetime experience to user model (#56)
- **user**: add endpoints for SSO workflows (#55)
- **user**: add google and github profile fields (#54)
- **user**: add unapproved user management endpoints (#53)
- **character-trait**: reverse currency for flaw traits (#52)
- **character-trait**: require currency for adding a trait (#51)
- **character-trait**: return full trait in value-options response
- **character_trait**: add DELETE to list of value options (#48)
- **character_trait**: add currency to delete endpoint (#47)
- **user**: add detailed name fields to model (#44)

### Fix

- **assets**: normalize upload filenames to ASCII-safe slugs
- **trait**: simplify trait model (#77)
- **character**: compute v4 willpower from courage (#71)
- **diceroll**: add desperation dice to quickrolls (#58)
- **quickroll**: require at least one trait (#57)
- **character-trait**: enforce unique names for custom traits (#50)
- **blueprint**: require sheet section id in Trait model (#49)
- **character_trait**: add name to trait value options (#46)
- **user**: enforce slugifying username (#45)
- **company**: add resources_modified_at field (#43)

### Refactor

- **services**: simplify services and improve concurrency (#90)
- **test**: add automatic DB cleanup and remove boilerplate (#89)
- **middleware**: simplify middleware and add rate limit tests (#88)
- **migrate**: rework S3 migration scripts (#82)
- **cli**: restructure CLI lib modules into class-based services (#81)
- **services**: optimize database query performance (#79)
- **docker**: two-stage build with non-root user (#61)
- **tasks**: improve scheduled task resilience (#60)

## v0.8.0 (2026-02-17)

### Feat

- **user-xp**: implement consistent permission management (#36)
- **character-trait**: consolidate value endpoints (#35)
- **character-trait**: add cost preview endpoints (#34)
- **company**: admin user created for all companies (#33)
- **options**: add asset enumerations to options (#31)
- **gameplay**: support 20 sided dice

### Fix

- **options**: add BlueprintTraitOrderBy to options (#40)
- **options**: correct errors in options endpoint (#39)
- **character**: remove date_killed from patch requests
- sort books and chapters by number (#32)
- remove asset_ids from campaign and character update and patch

### Refactor

- **urls**: fix typo in internal endpoint name

## v0.7.0 (2026-01-22)

### Feat

- handle archive of models with dependents (#26)
- add filters to developer list endpoint (#24)

### Fix

- **company**: improve company access controls (#25)
- **company**: disallow setting user_ids (#23)
- **admin**: improve developer creation response (#22)

## v0.6.0 (2026-01-18)

### Feat

- **admin**: add namespace to admin endpoints (#21)

### Fix

- remove oauth from openapi schema (#20)

## v0.5.0 (2026-01-18)

### Feat

- add static pages (#18)

## v0.4.0 (2026-01-17)

### Feat

- **saq**: add basic auth to saq admin interface (#16)
- **core**: add saq task queue support (#15)
- **users**: implement permissions for user post and patch (#14)
- **traits**: support company free trait changes setting (#12)
- **user**: support permissions for xp management (#10)
- **campaign**: add support for campaign management permissions (#9)

### Fix

- **logging**: include extras in standard log output (#17)
- **cli**: prevent error on missing api keys file (#7)

### Refactor

- fix typo in function name (#11)

## v0.3.0 (2026-01-13)

### Feat

- **rate-limit**: use x-forward-for header if no api key (#5)

### Fix

- **security**: require api key for system health endpoint (#6)

## v0.2.0 (2026-01-13)

### Feat

- release initial features (#1)
