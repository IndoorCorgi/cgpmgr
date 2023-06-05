## 概要
Raspberry Pi / Jetson Nano用電源管理、制御基板「[RPZ-PowerMGR](https://www.indoorcorgielec.com/products/rpz-powermgr/)」コントロールツールです。本ソフトウェアをインストール後にcgpmgrコマンドが使用できるようになり、以下のことが可能になります。

- RPZ-PowerMGR基板の設定の変更
- 電源ON/OFFするスケジュール日時の追加、削除、インポート、エクスポート
- Raspberry Pi / Jetson本体の消費電流の測定、エクスポート
- RPZ-PowerMGR基板のファームウェア更新

Raspberry PiやJetson Nanoは便利なシングルボードコンピュータですが、次のような悩みを持ったことはありませんか？

- USBケーブルを抜き差ししないと電源をON、OFFできない
- ネットワークや遠隔から電源をOFFできない
- インターネットに繋がっていないと時刻がずれる
- 決まった時間だけ起動して消費電力を抑えたい
- モバイルバッテリーで長時間運用したい
- どれくらい電力を消費しているか知りたい

電源管理、省電力運用に必要な機能を網羅している「[RPZ-PowerMGR](https://www.indoorcorgielec.com/products/rpz-powermgr/)」拡張基板を使えばこれらの問題を全て解決できます。

## 必要環境
### ハードウェア

- 40ピン端子を持つRaspberry Piシリーズ
- Jetson Nano

### OS
- Raspberry Pi OS
- JetPack4.6

## 動作確認済モデル
- Raspberry Pi 4 Model B
- Raspberry Pi 3 Model B/B+
- Raspberry Pi Zero W/WH
- Raspberry Pi Zero
- Jetson Nano Developer Kit B01
- Jetson Nano 2GB Developer Kit

## インストール

以下のコマンドでコントロールツールをインストール/アップグレードできます。取り付けやOSのセットアップ手順は[製品ページ](https://www.indoorcorgielec.com/products/rpz-powermgr/)を参照してください. 

`sudo python3 -m pip install -U cgpmgr`

## 使い方
コマンドラインから`cgpmgr -h`を実行することでオプションの解説が表示されます。シチュエーション別の使い方は、以下の解説記事をご参照下さい。

- [スイッチでRaspberry Piの電源ON/OFF](https://www.indoorcorgielec.com/resources/raspberry-pi/rpz-powermgr-switch/)
- [指定時刻にRaspberry Piの電源をON/OFF](https://www.indoorcorgielec.com/resources/raspberry-pi/rpz-powermgr-schedule/)
- [Raspberry Piの消費電力測定&モバイルバッテリー稼働時間の計算](https://www.indoorcorgielec.com/resources/raspberry-pi/rpz-powermgr-current/)
- [定期撮影Raspberry Piカメラをモバイルバッテリーで長期運用](https://www.indoorcorgielec.com/resources/raspberry-pi/rpz-powermgr-battery-camera/)
