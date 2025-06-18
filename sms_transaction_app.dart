import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:telephony/telephony.dart';

void main() {
  runApp(MyApp());
}

class MyApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Transaction SMS Filter',
      theme: ThemeData(
        primarySwatch: Colors.blue,
        visualDensity: VisualDensity.adaptivePlatformDensity,
      ),
      home: TransactionSmsScreen(),
    );
  }
}

class TransactionSmsScreen extends StatefulWidget {
  @override
  _TransactionSmsScreenState createState() => _TransactionSmsScreenState();
}

class _TransactionSmsScreenState extends State<TransactionSmsScreen> {
  final Telephony telephony = Telephony.instance;
  List<SmsMessage> transactionMessages = [];
  bool isLoading = false;
  
  // Common transaction keywords and sender patterns
  final List<String> transactionKeywords = [
    'debited', 'credited', 'transaction', 'payment', 'transfer',
    'withdrew', 'deposit', 'balance', 'account', 'bank',
    'upi', 'paid', 'received', 'sent', 'wallet'
  ];
  
  final List<String> bankSenders = [
    'SBIINB', 'HDFCBK', 'ICICIB', 'KOTAKBK', 'AXISBK',
    'PAYTM', 'GPAY', 'PHONEPE', 'AMAZONPAY', 'FREECHARGE'
  ];

  @override
  void initState() {
    super.initState();
    requestPermissions();
  }

  Future<void> requestPermissions() async {
    final status = await Permission.sms.request();
    if (status.isGranted) {
      loadTransactionMessages();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('SMS permission is required to read messages')),
      );
    }
  }

  Future<void> loadTransactionMessages() async {
    setState(() {
      isLoading = true;
    });

    try {
      List<SmsMessage> messages = await telephony.getInboxSms(
        columns: [SmsColumn.ADDRESS, SmsColumn.BODY, SmsColumn.DATE],
        sortOrder: [
          OrderBy(SmsColumn.DATE, sort: Sort.DESC),
        ],
      );

      List<SmsMessage> filteredMessages = messages.where((message) {
        return isTransactionMessage(message);
      }).toList();

      setState(() {
        transactionMessages = filteredMessages;
        isLoading = false;
      });
    } catch (e) {
      setState(() {
        isLoading = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error loading messages: $e')),
      );
    }
  }

  bool isTransactionMessage(SmsMessage message) {
    String body = message.body?.toLowerCase() ?? '';
    String sender = message.address?.toUpperCase() ?? '';
    
    // Check if sender matches known bank/payment gateway patterns
    bool isBankSender = bankSenders.any((bank) => sender.contains(bank));
    
    // Check if message contains transaction keywords
    bool hasTransactionKeywords = transactionKeywords.any((keyword) => 
        body.contains(keyword.toLowerCase()));
    
    // Check for currency symbols and amounts
    bool hasCurrencyPattern = body.contains(RegExp(r'₹|rs\.?\s*\d+|\$\d+'));
    
    return isBankSender || (hasTransactionKeywords && hasCurrencyPattern);
  }

  String formatDate(int? timestamp) {
    if (timestamp == null) return 'Unknown';
    DateTime date = DateTime.fromMillisecondsSinceEpoch(timestamp);
    return '${date.day}/${date.month}/${date.year} ${date.hour}:${date.minute.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Transaction Messages'),
        actions: [
          IconButton(
            icon: Icon(Icons.refresh),
            onPressed: loadTransactionMessages,
          ),
        ],
      ),
      body: isLoading
          ? Center(child: CircularProgressIndicator())
          : transactionMessages.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.message_outlined, size: 64, color: Colors.grey),
                      SizedBox(height: 16),
                      Text(
                        'No transaction messages found',
                        style: TextStyle(fontSize: 18, color: Colors.grey[600]),
                      ),
                      SizedBox(height: 8),
                      Text(
                        'Pull to refresh or check permissions',
                        style: TextStyle(color: Colors.grey[500]),
                      ),
                    ],
                  ),
                )
              : RefreshIndicator(
                  onRefresh: loadTransactionMessages,
                  child: ListView.builder(
                    itemCount: transactionMessages.length,
                    itemBuilder: (context, index) {
                      SmsMessage message = transactionMessages[index];
                      return Card(
                        margin: EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        child: ListTile(
                          leading: CircleAvatar(
                            backgroundColor: Colors.blue,
                            child: Icon(Icons.account_balance_wallet, color: Colors.white),
                          ),
                          title: Text(
                            message.address ?? 'Unknown Sender',
                            style: TextStyle(fontWeight: FontWeight.bold),
                          ),
                          subtitle: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                message.body ?? '',
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                              ),
                              SizedBox(height: 4),
                              Text(
                                formatDate(message.date),
                                style: TextStyle(
                                  color: Colors.grey[600],
                                  fontSize: 12,
                                ),
                              ),
                            ],
                          ),
                          onTap: () {
                            showDialog(
                              context: context,
                              builder: (BuildContext context) {
                                return AlertDialog(
                                  title: Text(message.address ?? 'Unknown Sender'),
                                  content: Column(
                                    mainAxisSize: MainAxisSize.min,
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        'Date: ${formatDate(message.date)}',
                                        style: TextStyle(fontWeight: FontWeight.bold),
                                      ),
                                      SizedBox(height: 8),
                                      Text(message.body ?? ''),
                                    ],
                                  ),
                                  actions: [
                                    TextButton(
                                      child: Text('Close'),
                                      onPressed: () {
                                        Navigator.of(context).pop();
                                      },
                                    ),
                                  ],
                                );
                              },
                            );
                          },
                        ),
                      );
                    },
                  ),
                ),
      floatingActionButton: FloatingActionButton(
        onPressed: loadTransactionMessages,
        child: Icon(Icons.sync),
        tooltip: 'Refresh Messages',
      ),
    );
  }
}