## 概要
Raspberry Pi用電源管理、制御基板「[RPZ-PowerMGR](https://www.indoorcorgielec.com/products/rpz-powermgr/)」コントロールツールです。本ソフトウェアをインストール後にcgpmgrコマンドが使用できるようになり、以下のことが可能になります。

- RPZ-PowerMGR基板の設定の変更
- 電源ON/OFFするスケジュール日時の追加、削除、インポート、エクスポート
- Raspberry Pi本体の消費電流の測定、エクスポート
- RPZ-PowerMGR基板のファームウェア更新

Raspberry Piは大変便利な小型コンピューターです。しかし、電源まわりには課題もあります。Raspberry Piを使っていて、次のような悩みを持ったことはありませんか？

- USBケーブルを抜き差ししないと電源をON、OFFできない
- ネットワークや遠隔から電源をOFFできない
- インターネットに繋がっていないと時刻がずれる
- 決まった時間だけ起動して消費電力を抑えたい
- モバイルバッテリーで長時間運用したい
- どれくらい電力を消費しているか知りたい

電源管理、省電力運用に必要な機能を網羅している「[RPZ-PowerMGR](https://www.indoorcorgielec.com/products/rpz-powermgr/)」拡張基板を使えばこれらの問題を全て解決できます。

## 必要環境
ハードウェア: 40ピン端子を持つRaspberry Piシリーズ \
OS: Raspberry Pi OS

## 動作確認済モデル
- Raspberry Pi 4 Model B
- Raspberry Pi 3 Model B/B+
- Raspberry Pi Zero W/WH
- Raspberry Pi Zero

## インストール

以下のコマンドでコントロールツールをインストール/アップグレードできます。具体的なセットアップ手順は[セットアップ(ハードウェア)](https://www.indoorcorgielec.com/products/rpz-powermgr/#%E3%82%BB%E3%83%83%E3%83%88%E3%82%A2%E3%83%83%E3%83%97%E3%83%8F%E3%83%BC%E3%83%89%E3%82%A6%E3%82%A7%E3%82%A2)、[セットアップ(ソフトウェア)](https://www.indoorcorgielec.com/products/rpz-powermgr/#%E3%82%BB%E3%83%83%E3%83%88%E3%82%A2%E3%83%83%E3%83%97%E3%82%BD%E3%83%95%E3%83%88%E3%82%A6%E3%82%A7%E3%82%A2)を参照して下さい。

`sudo python3 -m pip install -U cgpmgr`

## 使い方
コマンドラインから`cgpmgr -h`を実行することでオプションの解説が表示されます。シチュエーション別の使い方は、以下の解説記事をご参照下さい。

- [スイッチでRaspberry Piの電源ON/OFF](https://www.indoorcorgielec.com/resources/raspberry-pi/rpz-powermgr-switch/)
- [指定時刻にRaspberry Piの電源をON/OFF](https://www.indoorcorgielec.com/resources/raspberry-pi/rpz-powermgr-schedule/)
- [Raspberry Piの消費電力測定&モバイルバッテリー稼働時間の計算](https://www.indoorcorgielec.com/resources/raspberry-pi/rpz-powermgr-current/)
- [定期撮影Raspberry Piカメラをモバイルバッテリーで長期運用](https://www.indoorcorgielec.com/resources/raspberry-pi/rpz-powermgr-battery-camera/)
