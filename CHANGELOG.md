# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0](https://github.com/GaijinKa/juturna/compare/juturna-v1.0.2...juturna-v2.0.0) (2025-12-12)


### ⚠ BREAKING CHANGES

* new message freezing

### Features

* ([#21](https://github.com/GaijinKa/juturna/issues/21)) address requested changes from review ([68eff99](https://github.com/GaijinKa/juturna/commit/68eff99c3dc5a8415f1d7b2c815bc69db6269ea2))
* ([#21](https://github.com/GaijinKa/juturna/issues/21)) address requested changes from review ([0f9c70b](https://github.com/GaijinKa/juturna/commit/0f9c70b486ccc73f45f3843add9d3f42d9277fdd))
* add environment variable support for pipeline configurations ([9baf369](https://github.com/GaijinKa/juturna/commit/9baf369049deff97b51e3b3f594ea8ab1168c022))
* add environment variable support for pipeline configurations ([aed144e](https://github.com/GaijinKa/juturna/commit/aed144e056885512bbc8e52d7813404dcfef866d)), closes [#38](https://github.com/GaijinKa/juturna/issues/38)
* **audio_rtp:** make RTP encoding, clock rate, and channel count configurable in source node ([313e318](https://github.com/GaijinKa/juturna/commit/313e3187c60762222bf677525dd0b8cc9135f4c6))
* **buffer:** add buffer flush method ([1a0f7b1](https://github.com/GaijinKa/juturna/commit/1a0f7b1fe10c9d50d759b1b6e44e5e4ca3413c39))
* **buffer:** add buffer flush method ([be7041f](https://github.com/GaijinKa/juturna/commit/be7041f91e70712f56394eba570ecdfbf8b92c51))
* **ci:** automating trigger for release-please enabled ([a4b6a4e](https://github.com/GaijinKa/juturna/commit/a4b6a4ea1fd820641ca2e2ba9a97d55c82f7dfa9))
* **ci:** enabled release-please on test-main merge ([1562fa2](https://github.com/GaijinKa/juturna/commit/1562fa231555029630601de9160414a9c10007fd))
* **ci:** enabling testing release please ([e22a7cc](https://github.com/GaijinKa/juturna/commit/e22a7cc269344434c8db9765f79d54b197678a79))
* **ci:** improving release-please script ([f6ec2d4](https://github.com/GaijinKa/juturna/commit/f6ec2d486b8a24737bd5e1f520eecd04cf520f81))
* **ci:** improving release-please script ([eb020c3](https://github.com/GaijinKa/juturna/commit/eb020c3c5606b85705fd682973bd322423a873ed))
* **ci:** testing the release-please functionalities ([ad97b99](https://github.com/GaijinKa/juturna/commit/ad97b99f404a5c64d26d4530453652334de12d7f))
* **ci:** updating actions ([d7db30e](https://github.com/GaijinKa/juturna/commit/d7db30e13c9f0156afb4b1832ac84b6c7d3b7870))
* **ci:** updating actions ([d49e99f](https://github.com/GaijinKa/juturna/commit/d49e99f2887859fab27040702b177f21d603277e))
* handling subprocess unattended termination with possibly respawn in nodes/soruce/audio-rtp ([265c215](https://github.com/GaijinKa/juturna/commit/265c21587ba5e28401d99f71d935e54124d45a6b))
* make ffmpeg log level configurable  in nodes/soruce/audio-rtp ([29c1e90](https://github.com/GaijinKa/juturna/commit/29c1e90cf7b76c9e144bf5cd3ea03fc0eab3ead7))
* max queue size can be set through the JUTURNA_MAX_QUEUE_SIZE envar ([dc3f95f](https://github.com/GaijinKa/juturna/commit/dc3f95f6ad742d02ee075da4d00b200ecf951aed))
* new message freezing ([fe4cfe5](https://github.com/GaijinKa/juturna/commit/fe4cfe5fe1b5f81a82c3d87f44523c78373acd3a))
* **pipeline:** use DAG layers for deterministic node startup order ([49a9f4c](https://github.com/GaijinKa/juturna/commit/49a9f4ccd5afd998f25bfafbeb42a13a545865b3))
* **pipeline:** use DAG layers for deterministic node startup order ([d4f4cf6](https://github.com/GaijinKa/juturna/commit/d4f4cf6c582d39092accdd161c0915a2c6805b58))


### Bug Fixes

* ([#25](https://github.com/GaijinKa/juturna/issues/25)) inferring the incoming audio channels by parsing the encoding_clock_channel parameter ([3902cbe](https://github.com/GaijinKa/juturna/commit/3902cbe60008ecf393f5c0705d1ea3ec929996b5))
* adding the clear buffer function ([39b4a86](https://github.com/GaijinKa/juturna/commit/39b4a86fd2d074c63cf123d074dc9c8e371acde8))
* **audio_rtp:** ([#25](https://github.com/GaijinKa/juturna/issues/25)) Infer the incoming audio channels by parsing the encoding_clock_channel parameter ([eace777](https://github.com/GaijinKa/juturna/commit/eace77729571388201ebc03fdb752f5465527990))
* **audio_rtp:** ([#30](https://github.com/GaijinKa/juturna/issues/30)) improve process lifecycle management and restart handling ([fa3ad80](https://github.com/GaijinKa/juturna/commit/fa3ad80d4ad904d5a0929248c555972c0768b2de))
* **audio_rtp:** ([#32](https://github.com/GaijinKa/juturna/issues/32)) enforcing integers to automatic port assignment ([1cf8e6f](https://github.com/GaijinKa/juturna/commit/1cf8e6f1f8ebebdcbd196479fa373db21610bfaf))
* **audio_rtp:** ([#32](https://github.com/GaijinKa/juturna/issues/32)) enforcing integers to automatic port assignment ([d7578e6](https://github.com/GaijinKa/juturna/commit/d7578e6b3e9228530d5df397ac03aed6c9b3af43))
* **audio_rtp:** removing timeout from monitor_thread join ([fcfe338](https://github.com/GaijinKa/juturna/commit/fcfe3389defda95eccb43fa397a762fbb442557b))
* **audio_rtp:** removing timeout from monitor_thread join in order to avoid deadlocks on exiting ([0bce3b9](https://github.com/GaijinKa/juturna/commit/0bce3b92bd0e23d185625def83773e8328fe0680))
* buffer check log becomes a debug log ([c6298da](https://github.com/GaijinKa/juturna/commit/c6298da49c9bd947d3cd3d5daca426ba05efd3fd))
* **docs:** remove outdated LIFO queue documentation ([e454778](https://github.com/GaijinKa/juturna/commit/e4547783a065de6095a8ebf315cfb77e68b02984))
* exporting JUTURNA_MAX_QUEUE_SIZE correctly ([89e1996](https://github.com/GaijinKa/juturna/commit/89e19967f2b9eea2e5a39b6913505e9ba1938d58))
* JUTURNA_MAX_QUEUE_SIZE now is safe ([2539e6e](https://github.com/GaijinKa/juturna/commit/2539e6e3d5f961db3757f4b0df995b7b1dfc5b36))
* node.py's source thread termination must have a valid source_f ([a2ecea6](https://github.com/GaijinKa/juturna/commit/a2ecea6528acbefbdbbfbc4e6e3ec39ba23070cb))
* node.py's source thread termination must have a valid source_f ([40c3400](https://github.com/GaijinKa/juturna/commit/40c34009f368e987d186d782b164360d2d52bb09))
* **node:** output stuttering for videostream node ([31408ac](https://github.com/GaijinKa/juturna/commit/31408ace536cdbe1d857d129d9ab6b8d0abc85cd)), closes [#14](https://github.com/GaijinKa/juturna/issues/14)
* **notifier_udp:** udp packages now are chunked according to the header_size ([1416f48](https://github.com/GaijinKa/juturna/commit/1416f483a5d86fa543f109e4505f43d896d01add))
* now get_env_var receives a generic Type ([9aec61c](https://github.com/GaijinKa/juturna/commit/9aec61c5f5acf0140b1d6684221e82302b74da16))
* Remove default encoder from Node.dump_json method ([c96f052](https://github.com/GaijinKa/juturna/commit/c96f05213343705544d3bd2e9206ccdc172a7352))
* removing old starting approach (was already commented) ([12e48f3](https://github.com/GaijinKa/juturna/commit/12e48f3e29d5c1fba6b6da8172aadb880c7b9a66))
* removing stderr from subprocess in nodes/soruce/audio-rtp ([b915fb2](https://github.com/GaijinKa/juturna/commit/b915fb210eeb882a7ad0b74a5827ae6b8b728c27))
* replacing the LIFO queues with a FIFO to prevent misordering during burst ([8bfe611](https://github.com/GaijinKa/juturna/commit/8bfe6117b67934cdf4438ac32c21d96fb5feb994))
* restoring set_source insteaf of set_origin ([2e52fc9](https://github.com/GaijinKa/juturna/commit/2e52fc9103c9ae4d87ffdff4043509e27400215c))
* **transcriber_whispy:** derive start_abs from size and sequence_number ([f1cae64](https://github.com/GaijinKa/juturna/commit/f1cae64077c7bfaf30d5ebd900c1d4c6dacb6138))
* **transcriber_whispy:** derive start_abs from size and sequence_number ([d7e3089](https://github.com/GaijinKa/juturna/commit/d7e3089671ff6aadd8945f2c52d7e427c302edb1))
* **transcriber_whispy:** logging results ([03a1ef5](https://github.com/GaijinKa/juturna/commit/03a1ef5994849142e62727f3159d243d2a77f1f9))
* **transcriber_whispy:** logging results ([a031d4f](https://github.com/GaijinKa/juturna/commit/a031d4fd70b7a92793c318bb22ccc3d91201028e))
* **transcriber_whispy:** reverting start_abs fix using [@b3by](https://github.com/b3by)'s suggestions ([467ee55](https://github.com/GaijinKa/juturna/commit/467ee5518214b14b84199fee91bdfe4bacabed0f))


### Documentation

* adding the meetecho icon ([782de3c](https://github.com/GaijinKa/juturna/commit/782de3c4e28827c8f5f5e7e855216a7282e51b45))
* bumping peaceiris/actions-gh-pages version to 4 ([c58f5cc](https://github.com/GaijinKa/juturna/commit/c58f5cc62f48627814852a6e1848f18ccc9bf0c5))
* experimental using for custom.css ([2639cd4](https://github.com/GaijinKa/juturna/commit/2639cd4b8ec8382c1213d17f0edaab8378bb9ad2))
* navigation reorganized, added builder and publisher ([000bb6d](https://github.com/GaijinKa/juturna/commit/000bb6dd4a316e44209aa962c77e8d5618e41fb4))
* navigation reorganized, added builder and publisher ([b7a0834](https://github.com/GaijinKa/juturna/commit/b7a0834c519149127d6dc0defddea51e70f1d686))
* removed outdated LIFO queue documentation ([8dade49](https://github.com/GaijinKa/juturna/commit/8dade49e7552da39e618651d42fca370e524e09f))
* removing duplicate custom css and disabling the remaining one, removing the ./ path in conf.py ([9b9cec2](https://github.com/GaijinKa/juturna/commit/9b9cec2da43d50b3756601587802f6d9a3b8487b))
* removing explicit nojekyll touch, adding options in workflow ([e469bfe](https://github.com/GaijinKa/juturna/commit/e469bfe8f354fbdb17b8a20225a1c643584256b7))
* reverting the no nojekyll touch removal ([a03f851](https://github.com/GaijinKa/juturna/commit/a03f851ff9ef647c3f6712024010578b48ba93e1))
* reverting the no nojekyll touch removal, adding options in workflow ([26dde66](https://github.com/GaijinKa/juturna/commit/26dde66adf0025fcad683f4963a655659c48cf8d))
* revised description to focus on FIFO rationale and correct formatting ([6a7b1bc](https://github.com/GaijinKa/juturna/commit/6a7b1bcdf0695da67527e1fec5c747005e5189b4))
* updating the README.md and writing the intial draft for CONTRIBUTING.md ([dc428de](https://github.com/GaijinKa/juturna/commit/dc428de9e7251751e2806f5d5deb145d7c1cf071))


### Code Refactoring

* major review of audio rtp ([30965c8](https://github.com/GaijinKa/juturna/commit/30965c8e5c76a08349c43f1f8b6b5ad22bc03484))

## [Unreleased]



Releases up to version 1.0.2 were not tracked retroactively, so changelog entries start from subsequent versions
## [1.0.2] - 2025-11-27
