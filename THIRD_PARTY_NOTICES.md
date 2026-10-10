# Third-party assets and runtimes

The project source is MIT licensed. Third-party assets retain their own notices.

| Component | Upstream | License and local notice |
| --- | --- | --- |
| Tabler icon data | [Tabler Icons](https://github.com/tabler/tabler-icons), distributed through [Iconify icon sets](https://github.com/iconify/icon-sets) | MIT; `_SYSTEM/assets/github/tabler_LICENSE` |
| Four animated emoji assets | [Microsoft Fluent UI Emoji Animated](https://github.com/microsoft/fluentui-emoji-animated) | MIT; `_SYSTEM/assets/github/microsoft_LICENSE` |
| Noto Sans font | [Noto Fonts](https://github.com/notofonts/latin-greek-cyrillic) | SIL Open Font License 1.1; `_SYSTEM/framework/fonts/OFL.txt` |
| Optional speech weights (downloaded separately) | [Systran/faster-whisper-small](https://huggingface.co/Systran/faster-whisper-small) | MIT; pinned revision and checksums in `tools/speech_model_manifest.json` |

Asset provenance, pinned revisions and hashes are stored in `source.json` and
`animated_manifest.json` under `_SYSTEM/assets/github`. Keep the notices when
redistributing these assets. Blender, FFmpeg, Python and pip dependencies are
installed separately and retain their upstream licenses. The repository does not
bundle Blender/FFmpeg executables or speech model weights. Review the applicable
licenses when distributing an installed runtime or output containing third-party assets.
