# Changelog

## [0.1.5](https://github.com/yazouv/billiard-trajectory-tracer/compare/v0.1.4...v0.1.5) (2026-05-15)


### Features

* slider de seek, pacing au fps source, throttle Reglages ([4b90bb3](https://github.com/yazouv/billiard-trajectory-tracer/commit/4b90bb3816f869aa62ecc6ec2618cca0dd2e3c1f))


### Bug Fixes

* **config:** force Rectangle table et Bille rouge a Off au demarrage ([c53d699](https://github.com/yazouv/billiard-trajectory-tracer/commit/c53d699d4979225dbe0c4be52d2491bf6659adf0))
* cv2 pilote depuis tk.after() au lieu d'une boucle while concurrente ([d29a9d2](https://github.com/yazouv/billiard-trajectory-tracer/commit/d29a9d254c96cb0896b33eacec121383da3cd719))
* **launcher:** content avec expand=True pour ancrer les cards en haut ([1603591](https://github.com/yazouv/billiard-trajectory-tracer/commit/1603591892f3b5cfab02a85606a4e7a6d1269e5c))
* layout launcher (pas de side=bottom) + Reglages non-resizable ([0730d51](https://github.com/yazouv/billiard-trajectory-tracer/commit/0730d5182562acbe81753904d6dbae36e9cfac1a))
* **major:** rendu video dans tkinter via Pillow, plus de cv2.imshow ([2d881cc](https://github.com/yazouv/billiard-trajectory-tracer/commit/2d881ccad6471cce0e7d2ca6d06ede6b3bbdc425))
* traits qui clignotent + slider/play dans Reglages + crash updater ([3bd9be3](https://github.com/yazouv/billiard-trajectory-tracer/commit/3bd9be33fa019dd24303d80c10aa1337e2c2373b))


### Performance Improvements

* pipeline cv2 dans un thread worker, tk reste fluide ([a0093ec](https://github.com/yazouv/billiard-trajectory-tracer/commit/a0093ec4b32d70035826ebd61cf589dbfbee358b))

## [0.1.4](https://github.com/yazouv/billiard-trajectory-tracer/compare/v0.1.3...v0.1.4) (2026-05-15)


### Bug Fixes

* **exe:** pas de fenetre console + layout d'accueil corrige ([e0ada1c](https://github.com/yazouv/billiard-trajectory-tracer/commit/e0ada1c061756cec85ff4ce441601a7a163182ce))

## [0.1.3](https://github.com/yazouv/billiard-trajectory-tracer/compare/v0.1.2...v0.1.3) (2026-05-15)


### Features

* **launcher:** message gracieux si cyndilib ou NDI Runtime manquant ([cfe9abb](https://github.com/yazouv/billiard-trajectory-tracer/commit/cfe9abb632069f703387576b499d36d2dd22d0af))


### Bug Fixes

* **ci:** release-please build l'exe dans le meme workflow ([d95e94f](https://github.com/yazouv/billiard-trajectory-tracer/commit/d95e94fb652f0fa3f87aadda47ed1fccb24e8ee4))

## [0.1.2](https://github.com/yazouv/billiard-trajectory-tracer/compare/v0.1.1...v0.1.2) (2026-05-15)


### Features

* **updater:** installation auto en un clic (download + extract + relaunch) ([19a92a1](https://github.com/yazouv/billiard-trajectory-tracer/commit/19a92a1328113b39e455f94f4de2feb683829347))

## [0.1.1](https://github.com/yazouv/billiard-trajectory-tracer/compare/v0.1.0...v0.1.1) (2026-05-15)


### Bug Fixes

* **launcher:** footer disparu a cause de l'ordre du pack ([ba0d902](https://github.com/yazouv/billiard-trajectory-tracer/commit/ba0d902520e84d6905221aa005a5712b35c091ab))
