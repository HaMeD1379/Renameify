import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import 'theme.dart';

class PageFrame extends StatelessWidget {
  const PageFrame({
    required this.title,
    required this.icon,
    required this.child,
    this.actions = const [],
    super.key,
  });

  final String title;
  final IconData icon;
  final Widget child;
  final List<Widget> actions;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: colors.teal),
              const SizedBox(width: 10),
              Text(title, style: Theme.of(context).textTheme.headlineMedium),
              const Spacer(),
              ...actions.map(
                (item) => Padding(
                  padding: const EdgeInsets.only(left: 8),
                  child: item,
                ),
              ),
            ],
          ).animate().fadeIn(duration: 180.ms).slideY(begin: -0.03),
          const SizedBox(height: 16),
          Expanded(child: child.animate().fadeIn(duration: 220.ms)),
        ],
      ),
    );
  }
}

class Panel extends StatelessWidget {
  const Panel({
    required this.child,
    this.padding = const EdgeInsets.all(16),
    super.key,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(
        color: colors.panel,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: colors.line),
        boxShadow: [
          BoxShadow(
            color: colors.gold.withAlpha(10),
            blurRadius: 18,
            spreadRadius: -10,
          ),
        ],
      ),
      child: child,
    );
  }
}

class Metric extends StatelessWidget {
  const Metric({required this.label, required this.value, super.key});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return Container(
      constraints: const BoxConstraints(minWidth: 88),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: colors.panelAlt,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: colors.line),
        boxShadow: [
          BoxShadow(
            color: colors.gold.withAlpha(16),
            blurRadius: 16,
            spreadRadius: -12,
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: Theme.of(context).textTheme.bodySmall),
          Text(
            value,
            style: TextStyle(
              color: colors.goldSoft,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}

class Bucket extends StatelessWidget {
  const Bucket({required this.bucket, super.key});

  final String bucket;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final color = switch (bucket) {
      'High' => colors.green,
      'Low' => colors.orange,
      'Folder' => colors.blue,
      _ => colors.muted,
    };
    return Container(
      width: 70,
      alignment: Alignment.center,
      padding: const EdgeInsets.symmetric(vertical: 5),
      decoration: BoxDecoration(
        color: color.withAlpha(24),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withAlpha(110)),
      ),
      child: Text(bucket, style: TextStyle(color: color, fontSize: 11)),
    );
  }
}

class TableText extends StatelessWidget {
  const TableText(this.text, {required this.width, super.key});

  final String text;
  final double width;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: width,
      child: Text(text, maxLines: 1, overflow: TextOverflow.ellipsis),
    );
  }
}

class EmptyState extends StatelessWidget {
  const EmptyState({
    required this.icon,
    required this.title,
    this.detail,
    super.key,
  });

  final IconData icon;
  final String title;
  final String? detail;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: colors.teal.withAlpha(150), size: 42),
          const SizedBox(height: 10),
          Text(title, style: Theme.of(context).textTheme.titleMedium),
          if (detail != null) ...[
            const SizedBox(height: 6),
            Text(detail!, style: Theme.of(context).textTheme.bodySmall),
          ],
        ],
      ),
    );
  }
}

class SectionTitle extends StatelessWidget {
  const SectionTitle(
    this.text, {
    this.icon = LucideIcons.slidersHorizontal,
    super.key,
  });

  final String text;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return Row(
      children: [
        Icon(icon, color: colors.amber, size: 17),
        const SizedBox(width: 8),
        Text(text, style: Theme.of(context).textTheme.titleMedium),
      ],
    );
  }
}
